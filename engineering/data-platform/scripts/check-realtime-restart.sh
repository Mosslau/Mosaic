#!/usr/bin/env bash
# check-realtime-restart.sh — 「重启不丢窗口」自检（检查点 + 已提交位移恢复）
#
# 验证的命题（P1 的兑现项，2026-09-20）：
#   作业**被取消期间**产生的数据，在重新提交后仍然进结果表 —— 即窗口不因重启而断档。
#   机理两条，缺一不可：
#     ① 状态侧：检查点把窗口状态落 MinIO（重启后从最近检查点恢复）；
#     ② 位点侧：`scan.startup.mode = group-offsets` + 检查点完成时提交的位移
#       （重启后从**已提交位移**续读，而不是 latest 跳过停机期间的数据）。
#
# 判据为什么长这样（本仓踩过的坑都指向同一条纪律）：
#   - 判据必须落在**端到端事实**（停机期间的数据最终出现在结果表）上，不能用"配置里写了
#     group-offsets""检查点目录配了"这类**代理指标** —— 代理指标正是静默失效的温床：
#     P1 落地时 compose 上的检查点配置**根本没进 JobGraph**（作业 3 分钟 0 次检查点），
#     只看配置文件会得出完全相反的结论。
#   - 脚本自带**负向对照**：取消后注入，先断言"此时结果表里没有该码"，再断言注入后
#     `末尾位移 > 已提交位移`（确有其数据没被消费过）。没有这两条，第 ⑥ 步的 ✅ 可能只是
#     "停机期间压根没数据可丢"的假通过。
#
# 用法: bash scripts/check-realtime-restart.sh
# 退出码: 0 全部通过 / 1 有断言失败 / 2 前置不满足（集群或作业没起）
# 前置: 与 check-realtime-e2e.sh 相同（compose 起好 + init.sql 建表 + submit-jobs.sh 已提交）
#
# ⚠️ 副作用（如实记录）：为了让窗口尽快关闭，心跳用的是**未来 ts**（最多 +70s），
#   因此本检查会把 raw topic 的水位线推到墙钟时间之前最多约 2 分钟：**在此期间**其它生产者
#   （模拟器/网关）产生的数据会被当"迟到"丢弃。故本脚本只用于受控自检环境（CI 的 compose 作业里
#   排在 e2e 之后跑），不要在有真实流量时反复跑。
#
# 兼容性: macOS /bin/bash 是 3.2 —— 不用 declare -A；变量一律 ${...} 界定（裸 $VAR 后接全角字符会
#   被并进变量名，本仓已踩过两次）。
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REST="${FLINK_REST:-http://127.0.0.1:18088}"
KAFKA_CT="${KAFKA_CONTAINER:-ov-kafka}"
CH_CT="${CLICKHOUSE_CONTAINER:-ov-clickhouse}"
TIMEOUT="${RST_TIMEOUT:-180}"          # 每条断言各自的预算(秒)
JOBS=(ov-online-count-1m ov-fault-count-1m ov-high-temp-battery-1m)
FAULT_JOB=ov-fault-count-1m
GROUP=flink-realtime-fault-1m          # 作业②的消费组(位移恢复就靠它)
VIN_A=OVRST00001
VIN_B=OVRST00002
# 故障码**每轮唯一**(带 HHMMSS 后缀): 否则第二次运行时"停机期间结果表里没有该码"这条负向对照
# 必然失败 —— 上一轮已经写进去了(2026-09-20 实测: 复用固定码 RSTB1 时, 第二遍跑假红一次)。
RUN_TAG=$(date +%H%M%S)
CODE_A="RSTA${RUN_TAG}"                 # 阶段 A(停机前)的故障码
CODE_B="RSTB${RUN_TAG}"                 # 阶段 B(停机期间)的故障码 —— 本检查的主角
HB=OVRST00009                          # 推进水位线用的心跳 VIN

pass=0; fail=0
ok()   { echo "  ✅ $1"; pass=$((pass+1)); }
bad()  { echo "  ❌ $1"; fail=$((fail+1)); }
info() { echo "     $1"; }

ch()      { docker exec "${CH_CT}" clickhouse-client --user ov_admin --password ov_pass_2026 --query "$1"; }
produce() { docker exec -i "${KAFKA_CT}" /opt/kafka/bin/kafka-console-producer.sh \
              --bootstrap-server localhost:9092 --topic vehicle-report-raw >/dev/null 2>&1; }
num()     { ch "$1" 2>/dev/null | tr -d ' \n'; }
running() { curl -s --max-time 5 "${REST}/jobs/overview" 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)['jobs']
except Exception: d=[]
print(sum(1 for j in d if j.get('state')=='RUNNING'))" 2>/dev/null; }
jid_of()  { curl -s --max-time 5 "${REST}/jobs/overview" 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)['jobs']
except Exception: d=[]
print(next((j['jid'] for j in d if j.get('name')==sys.argv[1] and j.get('state')=='RUNNING'), ''))" "$1" 2>/dev/null; }
ckpt_done() { curl -s --max-time 5 "${REST}/jobs/$1/checkpoints" 2>/dev/null | python3 -c "
import json,sys
try: print(json.load(sys.stdin).get('counts',{}).get('completed',0))
except Exception: print(0)" 2>/dev/null; }
# 消费组位移: 输出 "<已提交合计> <末尾合计>"（末尾位移取自 --describe 的 LOG-END-OFFSET 列）
group_offsets() { docker exec "${KAFKA_CT}" /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 --describe --group "$1" 2>/dev/null \
    | awk 'NR>1 && $2=="vehicle-report-raw" {c+=$4; e+=$5} END {printf "%d %d\n", c+0, e+0}'; }
# 结果表里某故障码的行数（按码计, 与作业②口径一致）
code_rows() { num "SELECT count() FROM oceanverse.ads_fault_count_1m WHERE code='$1'"; }

# 注入一台车的故障 + 心跳, 心跳的 ts 是**未来**时刻(最多 +70s) → 水位线立刻越过窗口结束
# 窗口 = TUMBLE(ts, 1 MINUTE); WATERMARK 容忍 10s ⇒ 需要 max_ts ≥ 窗口结束 + 10s = T0 + 65s
inject() {   # $1=vin  $2=故障码
  local t0=$(( ($(date +%s) / 60) * 60 + 5 ))
  {
    echo "{\"vin\":\"$1\",\"ts\":${t0},\"type\":\"fault\",\"data\":{\"fault_codes\":[\"$2\"]}}"
    echo "{\"vin\":\"$1\",\"ts\":${t0},\"type\":\"fault\",\"data\":{\"fault_codes\":[\"$2\"]}}"   # QoS1 重复投递
    local i
    for i in 10 20 30 40 50 60 70; do
      echo "{\"vin\":\"${HB}\",\"ts\":$(( t0 + i )),\"type\":\"vehicle_status\",\"data\":{\"soc\":70}}"
    done
  } | produce
  echo "${t0}"
}
wait_rows() {   # $1=故障码  $2=最小行数  $3=描述
  local deadline=$(( $(date +%s) + TIMEOUT ))
  while [ "$(date +%s)" -lt "${deadline}" ]; do
    [ "$(code_rows "$1")" -ge "$2" ] 2>/dev/null && { ok "$3"; return 0; }
    sleep 5
  done
  bad "$3（${TIMEOUT}s 内未达标：code=$1 实测 $(code_rows "$1") 行）"
  return 1
}

echo "=== 实时层重启自检（检查点 + 位移恢复）==="

# ---------- 前置 ----------
n=$(running)
if [ "${n:-0}" != "3" ]; then
  echo "  ⚠️ 前置不满足: 正在运行的作业数 = ${n:-?}（应为 3）"
  echo "     先起集群与作业: docker compose -f deploy/docker-compose.yaml --profile realtime up -d && bash lakehouse/warehouse/streaming/submit-jobs.sh"
  exit 2
fi
tables=$(num "SELECT count() FROM system.tables WHERE database='oceanverse' AND name IN ('ads_vehicle_online_1m','ads_fault_count_1m','ads_high_temp_battery_1m')")
if [ "${tables:-0}" != "3" ]; then
  echo "  ⚠️ 前置不满足: ClickHouse 结果表不全（${tables:-?}/3）→ 先跑 init.sql"
  exit 2
fi
info "前置通过: 3 个作业 RUNNING、3 张结果表存在"
info "本轮标记: 故障码 ${CODE_A} / ${CODE_B}（每轮唯一, 避免与历史轮次混淆）"

# ---------- ① 阶段 A: 停机前注入, 证明"数据能流 + 位移会提交" ----------
T0_A=$(inject "${VIN_A}" "${CODE_A}")
info "阶段 A: 已注入 ${VIN_A}/${CODE_A}（ts=${T0_A}, 含 1 条 QoS1 重复）+ 未来 ts 心跳"
wait_rows "${CODE_A}" 1 "阶段 A 数据落表（作业在跑 ⇒ 链路通畅）" || true

JID=$(jid_of "${FAULT_JOB}")
if [ -z "${JID}" ]; then bad "取不到 ${FAULT_JOB} 的 jid，后续无法验证检查点"; else
  base=$(ckpt_done "${JID}")
  info "阶段 A: ${FAULT_JOB} 当前已完成检查点 ${base} 次, 等下一次（≤${TIMEOUT}s）"
  deadline=$(( $(date +%s) + TIMEOUT ))
  while [ "$(date +%s)" -lt "${deadline}" ]; do
    [ "$(ckpt_done "${JID}")" -gt "${base}" ] 2>/dev/null && break
    sleep 5
  done
  now=$(ckpt_done "${JID}")
  [ "${now}" -gt "${base}" ] 2>/dev/null && ok "检查点完成并递增（${base} → ${now}）—— 位移随之提交" \
                                        || bad "检查点未递增（仍 ${now}）→ 位移不会提交, 恢复会退化成 latest"
fi

# ---------- ② 取消三个作业, 记录取消时的位移 ----------
read -r CUR_AT_CANCEL END_AT_CANCEL <<< "$(group_offsets "${GROUP}")"
info "取消前位移: 已提交=${CUR_AT_CANCEL} 末尾=${END_AT_CANCEL}"
for j in "${JOBS[@]}"; do
  jid=$(jid_of "${j}")
  [ -n "${jid}" ] && curl -s -X PATCH "${REST}/jobs/${jid}?mode=cancel" >/dev/null 2>&1
done
sleep 5
n=$(running)
[ "${n:-1}" = "0" ] && ok "三个作业已取消（停机开始）" || bad "取消后仍有 ${n} 个作业 RUNNING"

# ---------- ③ 阶段 B: **停机期间**注入 + 负向对照 ----------
T0_B=$(inject "${VIN_B}" "${CODE_B}")
info "阶段 B: 停机中注入 ${VIN_B}/${CODE_B}（ts=${T0_B}）"
rows_down=$(code_rows "${CODE_B}")
[ "${rows_down:-1}" = "0" ] && ok "负向对照①: 停机期间结果表里没有 ${CODE_B}（确未提前进表）" \
                          || bad "负向对照①: 作业已停机, 结果表却有 ${rows_down} 行 ${CODE_B}（判据本身可疑）"
read -r CUR_STILL END_B <<< "$(group_offsets "${GROUP}")"
if [ "${END_B:-0}" -gt "${CUR_AT_CANCEL:-0}" ] 2>/dev/null; then
  ok "负向对照②: 末尾位移 ${END_B} > 取消时已提交位移 ${CUR_AT_CANCEL}（确有 $(( END_B - CUR_AT_CANCEL )) 条未消费数据, 恢复不可能来自 latest）"
else
  bad "负向对照②: 末尾位移 ${END_B} ≤ 取消时已提交位移 ${CUR_AT_CANCEL}（停机期间没有新数据, 本检查失去意义）"
fi
[ "${CUR_STILL}" = "${CUR_AT_CANCEL}" ] 2>/dev/null && info "停机期间已提交位移未变（${CUR_STILL}）: 没有消费者在读" \
                                                 || info "停机期间已提交位移 ${CUR_AT_CANCEL} → ${CUR_STILL}"

# ---------- ④ 重新提交, 断言停机期间的数据不丢 ----------
info "重新提交三个作业（submit-jobs.sh）"
bash "${ROOT}/lakehouse/warehouse/streaming/submit-jobs.sh" >/tmp/ov-restart-submit.log 2>&1
deadline=$(( $(date +%s) + TIMEOUT ))
while [ "$(date +%s)" -lt "${deadline}" ]; do
  [ "$(running)" = "3" ] && break
  sleep 5
done
n=$(running)
[ "${n:-0}" = "3" ] && ok "三个作业重新提交后 RUNNING" || { bad "重新提交后有 ${n:-0} 个作业 RUNNING（详见 /tmp/ov-restart-submit.log）"; }
wait_rows "${CODE_B}" 1 "停机期间的数据已进结果表（${CODE_B}）—— **窗口没因重启断档**" || true

# ---------- ⑤ 位移前进(补读完成) ----------
# 必须**轮询**: 位移只在检查点完成时提交(间隔 60s), 提交后立刻读会读到旧值 ——
# 第一版只读一次, 于是同一脚本第二遍跑报"位移未前进"的假红(2026-09-20 实测)。
read -r CUR_AFTER END_AFTER <<< "$(group_offsets "${GROUP}")"
deadline=$(( $(date +%s) + TIMEOUT ))
while [ "${CUR_AFTER:-0}" -le "${CUR_AT_CANCEL:-0}" ] 2>/dev/null && [ "$(date +%s)" -lt "${deadline}" ]; do
  sleep 5
  read -r CUR_AFTER END_AFTER <<< "$(group_offsets "${GROUP}")"
done
if [ "${CUR_AFTER:-0}" -gt "${CUR_AT_CANCEL:-0}" ] 2>/dev/null; then
  ok "位移已前进: ${CUR_AT_CANCEL} → ${CUR_AFTER}（末尾 ${END_AFTER}）"
else
  bad "位移未前进（等待 ${TIMEOUT}s 后仍 ${CUR_AFTER} ≤ ${CUR_AT_CANCEL}）"
fi

# ---------- ⑥ 幂等落表: 停机期间那条窗口"去重后恰好一行" ----------
# 目标表是 ReplacingMergeTree, 排序键 (window_start, code) 就是业务键 ⇒ FINAL 查询天然幂等。
# 不加 FINAL 的原始行数一并打出来: 大于 1 说明真有重复被写进去过(靠去重兜住), 也是有用信息。
rows_final=$(num "SELECT count() FROM oceanverse.ads_fault_count_1m FINAL WHERE code='${CODE_B}'")
rows_raw=$(num "SELECT count() FROM oceanverse.ads_fault_count_1m WHERE code='${CODE_B}'")
if [ "${rows_final:-0}" = "1" ]; then
  ok "幂等落表: ${CODE_B} 去重后恰好 1 行（原始 ${rows_raw} 行; 排序键 (window_start, code)）"
else
  bad "幂等落表: ${CODE_B} 去重后应为 1 行, 实测 ${rows_final} 行（原始 ${rows_raw} 行）"
fi

echo
if [ "${fail}" -gt 0 ]; then
  echo "==== 重启自检: ${fail} 项未通过（通过 ${pass} 项）===="
  exit 1
fi
echo "==== 重启自检: 全部通过（${pass} 项）===="
