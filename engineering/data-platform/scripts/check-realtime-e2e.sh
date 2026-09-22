#!/usr/bin/env bash
# check-realtime-e2e.sh — 实时层端到端自检（第 1 阶段第 3 步）
#
# 为什么需要它（2026-09-20 评估结论）:
#   在这之前, "实时链路通不通"**全靠人工验证** —— CI 只到"建表 + 提作业 + 断言作业 RUNNING",
#   并不验证数据真的落进 ADS 表。于是 SQL 语义/字段类型/时区这类问题一旦改坏, CI 照样全绿。
#   本脚本把那次人工验证固化成一条命令。
#
# 它验什么（每条都能失败, 不接受"看起来对"）:
#   ① 在线数: 窗口内去重车辆数 ≥ 注入的车辆数
#   ② 故障数: 同一条 (vin, ts, code) **注入两次** → fault_cnt 必须恰为 1（QoS1 去重是正确性前提）
#   ③ 高温电池: 注入 58℃ → level=alarm；47℃ → level=warn（阈值分级真的生效）
#   ④ 探针不污染: 三张表里不得出现 OVPROBE* 的行
#
# 注入方式: 直接往 Kafka raw topic 写契约 JSON（**不经网关**）——
#   这样它验的是"实时层"本身, 不依赖网关照常运行, 也不需要 dev token; CI 的 compose 作业里可直接跑。
#
# 测试数据命名空间（重要, 别和业务数据混淆）:
#   VIN 用 `OVE2E*`、故障码用 `E2E01` —— 属**自检保留段**, 会真实落进 ADS 表(它是"测试流量", 不是探针)。
#   注意与 `OVPROBE*` 的区别: 探针会被 Flink 过滤掉(用途是验链路活性), 而自检数据必须**流到底**才能断言。
#
# 退出码: 0=全过; 1=有断言不成立; 2=前置不满足(集群/表/作业没就绪, 属环境问题不是缺陷)
#
# 用法: bash scripts/check-realtime-e2e.sh
#       E2E_TIMEOUT=240 bash scripts/check-realtime-e2e.sh   # 放宽容差(默认 180s)
set -uo pipefail
# 兼容性注: 本机 /bin/bash 是 3.2 —— 裸 $VAR 后跟全角字符会被并进变量名
#   (踩过三次: `$T）` 报 `T: unbound variable`), 故本脚本变量一律 ${...} 界定。

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REST="${FLINK_REST:-http://127.0.0.1:18088}"
KAFKA_CT="${KAFKA_CONTAINER:-ov-kafka}"
CH_CT="${CLICKHOUSE_CONTAINER:-ov-clickhouse}"
TIMEOUT="${E2E_TIMEOUT:-240}"   # 每条断言各自的预算(心跳 120s 之后开始计时)
JOBS=(ov-online-count-1m ov-fault-count-1m ov-high-temp-battery-1m)
VEHICLES=(OVE2E00001 OVE2E00002 OVE2E00003 OVE2E00004 OVE2E00005)

pass=0; fail=0; skip=0
ok()   { echo "  ✅ $1"; pass=$((pass+1)); }
bad()  { echo "  ❌ $1"; fail=$((fail+1)); }
info() { echo "     $1"; }

ch() { docker exec "${CH_CT}" clickhouse-client --user ov_admin --password ov_pass_2026 --query "$1"; }
produce() { docker exec -i "${KAFKA_CT}" /opt/kafka/bin/kafka-console-producer.sh \
              --bootstrap-server localhost:9092 --topic vehicle-report-raw >/dev/null 2>&1; }

echo "=== 实时层端到端自检 ==="

# ---------- 前置: 作业在跑 / 表存在 ----------
running=$(curl -s --max-time 5 "${REST}/jobs/overview" 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)['jobs']
except Exception: d=[]
print(sum(1 for j in d if j.get('state')=='RUNNING'))" 2>/dev/null)
if [ "${running:-0}" != "3" ]; then
  echo "  ⚠️ 前置不满足: 正在运行的作业数 = ${running:-?}（应为 3）"
  echo "     先起集群与作业: docker compose -f deploy/docker-compose.yaml --profile realtime up -d && bash lakehouse/warehouse/streaming/submit-jobs.sh"
  exit 2
fi
for j in "${JOBS[@]}"; do
  curl -s --max-time 5 "${REST}/jobs/overview" | grep -q "\"name\":\"${j}\"" || { echo "  ⚠️ 前置不满足: 缺少作业 ${j}"; exit 2; }
done
tables=$(ch "SELECT count() FROM system.tables WHERE database='oceanverse' AND name IN ('ads_vehicle_online_1m','ads_fault_count_1m','ads_high_temp_battery_1m')" 2>/dev/null)
if [ "${tables:-0}" != "3" ]; then
  echo "  ⚠️ 前置不满足: ClickHouse 结果表不全（${tables}/3）"
  echo "     先建表: docker exec -i ov-clickhouse clickhouse-client --user ov_admin --password ov_pass_2026 --multiquery < lakehouse/warehouse/streaming/clickhouse/init.sql"
  exit 2
fi
info "前置通过: 3 个作业 RUNNING、3 张结果表存在"

# ---------- 注入 ----------
# 不等整分钟边界 —— 断言只要求"窗口起点 ≥ 注入那一分钟"(见下面 W 的判据), 与是否对齐边界无关。
# 旧版等边界(最多 60s)是纯空等, 已去掉(2026-09-20 提速: compose 作业里这步占全场 80%)。
T=$(date +%s); W0=$(( T / 60 * 60 ))
echo "  注入测试数据（窗口起点 $(date -r "${W0}" '+%H:%M:%S' 2>/dev/null || date -d "@${W0}" '+%H:%M:%S'), ts=${T}）"
{
  for v in "${VEHICLES[@]}"; do
    echo "{\"vin\":\"${v}\",\"ts\":${T},\"type\":\"vehicle_status\",\"data\":{\"soc\":70,\"temp_max\":30}}"
  done
  # 故障: 同一条 (vin, ts, E2E01) 发两次 → 期望 fault_cnt == 1
  echo "{\"vin\":\"OVE2E00001\",\"ts\":${T},\"type\":\"fault\",\"data\":{\"fault_codes\":[\"E2E01\"]}}"
  echo "{\"vin\":\"OVE2E00001\",\"ts\":${T},\"type\":\"fault\",\"data\":{\"fault_codes\":[\"E2E01\"]}}"
  # 高温: alarm(58) 与 warn(47)
  echo "{\"vin\":\"OVE2E00002\",\"ts\":${T},\"type\":\"battery_status\",\"data\":{\"temp_max\":58,\"soc\":60}}"
  echo "{\"vin\":\"OVE2E00003\",\"ts\":${T},\"type\":\"battery_status\",\"data\":{\"temp_max\":47,\"soc\":60}}"
} | produce
info "已注入 5 台车状态 + 2 条重复故障 + 2 条高温（alarm/warn）"

# 心跳: 推进 watermark 让窗口关闭。窗口 = [W0, W0+60), watermark 容忍 10s
# ⇒ 只要事件时间推过 W0+70 窗口就会触发; 故心跳次数**按需算**(2~7 次), 不再固定 12 次(旧版固定 120s 空等)。
HB_N=$(( (W0 + 70 - T + 9) / 10 ))
for i in $(seq 1 "${HB_N}"); do
  ts=$(( T + i * 10 ))
  echo "{\"vin\":\"OVE2E00009\",\"ts\":${ts},\"type\":\"vehicle_status\",\"data\":{\"soc\":70}}"
  sleep 10
done | produce &
hb=$!
sleep 1
info "心跳 ${HB_N} 次（按需: 事件时间推到 W0+70=${W0}+70, 约 $(( HB_N * 10 ))s）"

# ---------- 等待落表 + 断言 ----------
# 先让心跳把 watermark 推完（窗口要到"窗口结束 + 10s 容忍"之后才会触发），再开始按各自预算轮询。
wait "${hb}" 2>/dev/null || true
info "心跳结束，等待窗口落表（每条断言各自轮询，最多 ${TIMEOUT}s）"

# 四条断言**共享一个截止时间**、在同一个循环里轮询（各自串行 240s 会让最坏耗时到十几分钟）。
# 比较一律用 **epoch**: 实测 `window_start >= toDateTime(epoch)` 这种跨时区比较不可靠。
W="toUnixTimestamp(window_start) >= ${W0}"
num() { ch "$1" 2>/dev/null | tr -d ' \n'; }

deadline=$(( $(date +%s) + TIMEOUT ))
A=""; B=""; C1=""; C2=""; P=""
while [ "$(date +%s)" -lt "${deadline}" ]; do
  A=$(num  "SELECT max(online_cnt) FROM oceanverse.ads_vehicle_online_1m WHERE ${W}")
  B=$(num  "SELECT count() FROM oceanverse.ads_fault_count_1m WHERE code='E2E01' AND ${W} AND fault_cnt=1 AND vehicle_cnt=1")
  C1=$(num "SELECT count() FROM oceanverse.ads_high_temp_battery_1m WHERE vin='OVE2E00002' AND ${W} AND level='alarm' AND temp_max >= 55")
  C2=$(num "SELECT count() FROM oceanverse.ads_high_temp_battery_1m WHERE vin='OVE2E00003' AND ${W} AND level='warn' AND temp_max >= 45 AND temp_max < 55")
  P=$(num  "SELECT (SELECT count() FROM oceanverse.ads_fault_count_1m WHERE code LIKE 'OVPROBE%')
                  + (SELECT count() FROM oceanverse.ads_high_temp_battery_1m WHERE vin LIKE 'OVPROBE%')")
  [ "${A:-0}" -ge "${#VEHICLES[@]}" ] 2>/dev/null && [ "${B:-0}" -ge 1 ] 2>/dev/null \
    && [ "${C1:-0}" -ge 1 ] 2>/dev/null && [ "${C2:-0}" -ge 1 ] 2>/dev/null && break
  sleep 6
done
info "轮询结束: online_max=${A:-?} 去重命中=${B:-?} alarm=${C1:-?} warn=${C2:-?} 探针=${P:-?}"

# ① 在线数
if [ "${A:-0}" -ge "${#VEHICLES[@]}" ] 2>/dev/null; then
  ok "在线数: 窗口内去重车辆数 max=${A} ≥ ${#VEHICLES[@]}（注入车辆数）"
else
  bad "在线数: 期望 ≥ ${#VEHICLES[@]} 台, 实测 '${A:-无数据}'（等了 ${TIMEOUT}s）"
fi

# ② 故障数 + QoS1 去重（同一条注入两次 → 必须恰为 1 次）
if [ "${B:-0}" -ge 1 ] 2>/dev/null; then
  ok "故障数 + QoS1 去重: 同一条注入 2 次 → fault_cnt=1 / vehicle_cnt=1"
else
  actual=$(ch "SELECT max(fault_cnt), max(vehicle_cnt) FROM oceanverse.ads_fault_count_1m WHERE code='E2E01' AND ${W}" 2>/dev/null | tr '\t' '/')
  bad "故障数去重: 期望 fault_cnt/vehicle_cnt = 1/1, 实测 '${actual:-无数据}'（2 次注入被算成 2 次即去重失效）"
fi

# ③ 高温分级（58→alarm 且 ≥55；47→warn 且 ∈[45,55)）
if [ "${C1:-0}" -ge 1 ] 2>/dev/null && [ "${C2:-0}" -ge 1 ] 2>/dev/null; then
  ok "高温分级: 58℃ → alarm（temp_max≥55）, 47℃ → warn（45≤temp_max<55）"
else
  bad "高温分级: alarm=${C1:-无}/warn=${C2:-无}（期望各 ≥1 条且分级正确）"
fi

# ④ 探针不污染
if [ "${P:-1}" = "0" ]; then
  ok "探针不污染: 结果表里 OVPROBE* 行数为 0"
else
  bad "探针污染: 结果表里出现 OVPROBE* 行（${P:-?}）—— 检查 SQL 里的过滤条件"
fi

echo
if [ "${fail}" -gt 0 ]; then
  echo "==== 实时层自检: ${fail} 项不成立 ===="
  exit 1
fi
echo "==== 实时层自检: 全部通过（${pass} 项）===="
