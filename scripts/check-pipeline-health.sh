#!/usr/bin/env bash
# check-pipeline-health.sh — 接入链路健康自检（含 Q11 僵尸消费组判据）
#
# 为什么需要它（2026-09-18 实测教训）:
#   评测期间被"新 codec 实例 /metrics 计数恒 0，但消费组 LAG=0、Kafka offset 在涨"
#   这个组合迷惑了十几分钟 —— 真因是早期 `go run` 残留的**孤儿 codec 进程**仍持有分区，
#   于是"消息被消费了"（真）与"这个实例什么都没消费"（也真）同时成立。
#   `docker compose ps` 全绿、Prometheus target 全 up、lag=0 —— 常规检查**全部看不出来**。
#   本脚本把那次的判据固化成一条命令。
#
# 判据（任一命中即视为异常）:
#   1. 消费组有 >1 个成员 —— 单副本部署下应恒为 1（多副本横扩时用 -m 放宽）
#   2. 同一分区的归属出现在多个成员上（僵尸成员占位）
#   3. 某服务的监听端口被 >1 个进程占住（疑似孤儿实例；lsof 的命令名会被截断, 故按端口判）
#   4. /metrics 的 consumed 计数在观测窗口内冻结（空闲时自动灌少量合法帧做强判据;
#      会真实经过链路, 故 consumed/decoded 计数会小幅增加 —— 属预期, 不是异常）
#
# 退出码: 0=全部正常; 1=发现异常（可直接进 CI/巡检）
#
# 用法:
#   bash scripts/check-pipeline-health.sh              # 默认观测 12s、期望单副本
#   bash scripts/check-pipeline-health.sh -w 30        # 观测 30s
#   bash scripts/check-pipeline-health.sh -m           # 允许多副本（横扩后）
#   可用环境变量覆盖: KAFKA_CONTAINER / CODEC_GROUP / CODEC_SRC_TOPIC /
#                     CODEC_METRICS / GATEWAY_METRICS / CODEC_PROC / GATEWAY_PROC / PROM_URL
set -uo pipefail

WINDOW=12
ALLOW_MULTI=0
PROBE="${PROBE:-1}"   # 空闲时是否灌少量合法探针帧做强判据(会真实经过链路)
KAFKA_CONTAINER="${KAFKA_CONTAINER:-ov-kafka}"
GROUP="${CODEC_GROUP:-device-codec-v1}"
SRC_TOPIC="${CODEC_SRC_TOPIC:-ov.raw.binary.v1}"
CODEC_METRICS="${CODEC_METRICS:-http://localhost:18090}"
GATEWAY_METRICS="${GATEWAY_METRICS:-http://localhost:18081}"
PROM_URL="${PROM_URL:-http://localhost:9090}"
CODEC_PROC="${CODEC_PROC:-device-codec}"
GATEWAY_PROC="${GATEWAY_PROC:-device-gateway}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -w|--window) WINDOW="${2:?}"; shift 2;;
    -m|--allow-multi) ALLOW_MULTI=1; shift;;
    -h|--help) sed -n '2,24p' "$0"; exit 0;;
    *) echo "未知参数: $1 (-h 看用法)" >&2; exit 2;;
  esac
done

pass=0; fail=0
ok()   { echo "  [OK]   $1"; pass=$((pass+1)); }
bad()  { echo "  [FAIL] $1"; fail=$((fail+1)); }
info() { echo "         $1"; }

kafka() { docker exec "$KAFKA_CONTAINER" /opt/kafka/bin/"$@" 2>/dev/null; }

# 前置: Kafka CLI 是否可用。区分"没有成员"与"命令/容器不存在"——
# 二者在旧版实现里都会表现为空输出, 容易误判。
if ! kafka kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
  echo "  [FAIL] 无法通过 docker exec ${KAFKA_CONTAINER} 调用 Kafka CLI（容器名/镜像/路径不对?）"
  echo "         提示: 本机容器名是 ov-kafka, CI(GitHub service container) 是 kafka —— 用 KAFKA_CONTAINER 覆盖"
  echo; echo "==== 自检结果: 前置检查未通过, 后续判据不可信 ===="
  exit 1
fi
metric() { curl -s -m 3 "$1/metrics" 2>/dev/null | awk -v k="$2" '$1==k {print $2}'; }
metric_sum() { curl -s -m 3 "$1/metrics" 2>/dev/null | awk -v re="$2" '$0 ~ re {s+=$2} END {print s+0}'; }

alert_count() {
  curl -s -m 3 "${PROM_URL}/api/v1/alerts" 2>/dev/null \
    | python3 -c "import json,sys;print(len(json.load(sys.stdin)['data']['alerts']))" 2>/dev/null
}

echo "=== OceanVerse 链路健康自检 ==="
echo "观测窗口: ${WINDOW}s | 消费者组: ${GROUP} | 主题: ${SRC_TOPIC}"
echo

# 探针注入前先快照告警状态: 本脚本第 4 步会灌合法帧, 会真实改变 consumed/decoded;
# 若环境里本就有未消退的历史告警(如刚跑过故障演练), 不能算本次自检失败。
ALERTS_BEFORE=$(alert_count)

# ---------- 1. 消费组成员数 ----------
echo "1) 消费组成员（单副本部署下应恒为 1）"
members_out=$(kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group "$GROUP" --members)
# 输出首行可能是空行, 第二行是表头(GROUP CONSUMER-ID ...) —— 必须显式跳过,
# 否则表头会被当成一个"成员"(实测踩过: 误报成员数 = 2)
member_ids=$(printf '%s\n' "$members_out" | awk 'NF>3 && $1!="GROUP" {print $2}' | sort -u)
member_n=$(printf '%s\n' "$member_ids" | grep -c . || true)

if [[ "$member_n" -eq 0 ]]; then
  bad "消费组 ${GROUP} 没有成员（codec 未运行? 或启动后未加入组）"
elif [[ "$member_n" -eq 1 ]]; then
  ok "成员数 = 1"
elif [[ "$ALLOW_MULTI" -eq 1 ]]; then
  ok "成员数 = ${member_n}（已用 -m 允许横扩）"
else
  bad "成员数 = ${member_n}（期望 1）→ 疑似僵尸成员（Q11）"
  printf '%s\n' "$member_ids" | sed 's/^/         /'
  info "处置: 杀掉孤儿进程 → 等会话超时(约 1 分钟, --state 变 Empty) → 再启单个实例"
fi

# ---------- 2. 同一分区是否被多个成员持有 ----------
echo "2) 分区归属（同一分区不得出现在多个成员上）"
assign_out=$(kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group "$GROUP")
dup=$(printf '%s\n' "$assign_out" | awk 'NF>3 && $1!="GROUP" && $2!="" && $3!="" {print $2"-"$3}' | sort | uniq -d)
if [[ -z "$dup" ]]; then
  ok "无重复分区归属"
else
  bad "以下分区被多个成员同时持有: $(printf '%s' "$dup" | tr '\n' ' ')"
fi

# ---------- 3. 服务存活 + 孤儿实例 ----------
echo "3) 服务存活与孤儿实例"
# 判据分两层, 因为它们的**可靠性不同**(2026-09-18 CI 实测教训):
#   ① 存活: 用 curl 探端点 —— 跨平台可靠, 无论进程跑在宿主还是容器里;
#   ② 孤儿: 用 lsof 数"占住监听端口的进程数" —— 在**本机**(宿主进程)可靠,
#      但在 CI(runner 上跑 --network host 的容器)上 lsof 可能看不到该 socket,
#      此时必须报"无法判定"而**不是**误报"未运行"(早期版本正是这样把工具/环境限制
#      伪装成服务故障, 白烧了两轮 CI)。
svc_url() { case "$1" in gateway) echo "${GATEWAY_METRICS}/metrics";; codec) echo "${CODEC_METRICS}/health";; esac; }

# lsof 判据用"实际能否执行"而不是 command -v: PATH 里存在同名但不可执行的占位脚本时,
# command -v 会返回成功而实际调用失败(测试 lsof 缺失场景时踩到)。
# lsof 退出码 1 = 没有匹配项, 说明 lsof 本身可用。
LSOF_OK=0
lsof -nP -iTCP:1 -sTCP:LISTEN >/dev/null 2>&1
case $? in 0|1) LSOF_OK=1;; esac

inconclusive=0
for pair in "gateway:18080" "codec:18090"; do
  role="${pair%%:*}"; port="${pair##*:}"
  url=$(svc_url "$role")
  if curl -sf -m 5 "$url" >/dev/null 2>&1; then
    alive=1
  else
    alive=0
  fi
  n=-1
  pids=""
  if [[ "$LSOF_OK" -eq 1 ]]; then
    pids=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u | tr '\n' ' ')
    n=$(printf '%s' "$pids" | wc -w | tr -d ' ')
  fi
  if [[ "$alive" -eq 0 ]]; then
    bad "${role}: 端点不可达（${url}）→ 未运行或未就绪"
  elif [[ "$n" -eq 1 ]]; then
    ok "${role}: 端点可达且仅 1 个进程占住端口 ${port} (pid ${pids})"
  elif [[ "$n" -gt 1 ]]; then
    bad "${role}: ${n} 个进程占住端口 ${port} → 疑似孤儿实例（Q11 根因）: ${pids}"
    info "处置: go run 的包装进程被杀会留下编译产物孤儿（占消费组/端口）; 请用 go build 出的二进制起服务"
  else
    # 端点通 = 服务确实活着; lsof 看不到 → 环境限制, 不是故障
    ok "${role}: 端点可达（${url}）"
    why="常见于容器 --network host 环境"
    [[ "$LSOF_OK" -eq 0 ]] && why="lsof 不可用"
    info "lsof 看不到该端口的监听进程（${why}）→ 孤儿判据无法判定"
    inconclusive=1
  fi
done
[[ "$inconclusive" -eq 1 ]] && info "提示: K8s/容器环境无宿主进程概念, 孤儿判据请以『消费组成员数』(判据 1) 为准"

# ---------- 4. consumed 计数活性 ----------
echo "4) codec 计数活性（冻结的计数 + topic 有新消息 = 消息被别的进程消费了）"
c0=$(metric "$CODEC_METRICS" codec_consumed_total)
if [[ -z "$c0" ]]; then
  bad "读不到 codec_consumed_total（${CODEC_METRICS}/metrics 不可达?）"
else
  end0=$(kafka kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic "$SRC_TOPIC" | awk -F: '{s+=$3} END {print s+0}')
  sleep "$WINDOW"
  c1=$(metric "$CODEC_METRICS" codec_consumed_total)
  end1=$(kafka kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic "$SRC_TOPIC" | awk -F: '{s+=$3} END {print s+0}')
  lag=$(metric "$CODEC_METRICS" codec_consumer_lag)
  info "consumed: ${c0} -> ${c1} | topic LOG-END: ${end0} -> ${end1} | lag=${lag:-?}"
  if [[ "$c1" != "$c0" ]]; then
    ok "consumed 在增长（本实例确实在消费）"
  elif [[ "$end1" != "$end0" ]]; then
    bad "topic 有新消息（+$((end1-end0))）但本实例 consumed 冻结 → 消息被别的进程消费了（Q11 判据）"
  elif [[ "${lag:-0}" -gt 0 ]]; then
    bad "consumed 冻结且 lag=${lag} > 0 → 本实例卡住（查 flush 是否阻塞 / Kafka 是否可写）"
  elif [[ "${PROBE:-1}" -eq 1 ]]; then
    # 空闲态无法区分"真健康"与"僵尸占位" —— 主动灌少量**合法**帧做强判据。
    # 为什么用 bin-simulator 而不是手写载荷: 手写 "##probe" 这类非法帧会让 codec
    # 进 DLQ, 从而触发 CodecDLQGrowing 告警 —— 探针自己制造告警(实测踩过)。
    # 合法帧走 decode→写出→提交的正常路径, 只动 consumed 计数。
    info "无新消息, 灌少量合法探针帧以做强判据..."
    if docker exec ov-emqx emqx ctl status >/dev/null 2>&1 && \
       (cd "$(dirname "$0")/../ingest/device-simulator" 2>/dev/null && \
        GOCACHE="${GOCACHE:-/tmp/ov-health-gocache}" timeout 60 go run ./cmd/bin-simulator \
          -broker "tcp://localhost:${EMQX_MQTT_PORT:-11883}" -devices 2 -interval 1s -duration 3s >/dev/null 2>&1); then
      sleep 4
      c2=$(metric "$CODEC_METRICS" codec_consumed_total)
      if [[ "$c2" != "$c1" ]]; then
        ok "探针帧被本实例消费（consumed ${c1} -> ${c2}）"
      else
        bad "探针帧未被本实例消费（consumed 仍为 ${c2}）→ 疑似僵尸成员占位（Q11 判据）"
      fi
    else
      info "探针注入失败（EMQX 不可达或模拟器不可用）, 跳过强判据（不计失败）"
    fi
  else
    ok "无新消息且 consumed 冻结（空闲态; PROBE=0 已跳过强判据）"
  fi
fi

# ---------- 5. 网关受理 vs 落盘 ----------
echo "5) 网关受理 vs 落盘（同步投递下应逐条相等）"
req=$(metric_sum "$GATEWAY_METRICS" '^gateway_requests_total.*result="ok"')
wok=$(metric_sum "$GATEWAY_METRICS" '^gateway_kafka_write_total.*result="ok"')
werr=$(metric_sum "$GATEWAY_METRICS" '^gateway_kafka_write_total.*result="error"')
if [[ "$req" -eq 0 && "$wok" -eq 0 ]]; then
  bad "读不到网关指标（${GATEWAY_METRICS}/metrics 不可达?）"
else
  info "受理=${req} 落盘=${wok} 写失败=${werr}"
  if [[ "$req" -eq "$wok" ]]; then ok "受理 == 落盘"; else bad "受理(${req}) != 落盘(${wok}) → 差 $((req-wok)) 条未落盘"; fi
  if [[ "$werr" -eq 0 ]]; then ok "无写失败"; else bad "存在 ${werr} 条写失败（看网关日志与 Kafka 可用性）"; fi
fi

# ---------- 6. 告警状态 ----------
echo "6) Prometheus 告警（自检前后应无**新增**告警）"
ALERTS_AFTER=$(alert_count)
if [[ -z "$ALERTS_AFTER" ]]; then
  info "Prometheus 不可达，跳过（不计失败）"
elif [[ -z "$ALERTS_BEFORE" ]]; then
  info "起点快照不可用，仅报告当前: ${ALERTS_AFTER} 条"
elif [[ "$ALERTS_AFTER" -eq 0 ]]; then
  ok "无 firing 告警"
elif [[ "$ALERTS_AFTER" -le "$ALERTS_BEFORE" ]]; then
  ok "无**新增**告警（自检前已有 ${ALERTS_BEFORE} 条未消退）"
  info "既有告警详情: curl ${PROM_URL}/api/v1/alerts （本机无 Alertmanager, 需主动看）"
else
  bad "告警数由 ${ALERTS_BEFORE} 增至 ${ALERTS_AFTER} → 自检期间出现新告警（curl ${PROM_URL}/api/v1/alerts 看详情）"
fi

echo
echo "==== 自检结果: 通过 ${pass} 项, 异常 ${fail} 项 ===="
if [[ "$fail" -ne 0 ]]; then
  echo "提示: 异常项处置见 deploy/README Q11(僵尸消费组)/Q13(Kafka 监听器)/Q15(自愈)/Q16(告警)"
fi
exit $(( fail > 0 ))
