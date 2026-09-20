#!/usr/bin/env bash
# submit-jobs.sh — 把 warehouse/streaming/sql/ 下的三个 Flink SQL 作业提交到 session cluster
#
# 为什么用**独立的短命容器**提交, 而不是 `docker exec` 进 JobManager:
#   2026-09-20 实测 —— 在 512m 的 JM 容器里跑 sql-client(第二个 JVM)会挤爆同一个 cgroup 触发 OOM
#   (`docker events --filter event=oom` 有 ov-flink-jm 的 oom 事件), 症状是"提交到一半容器重启",
#   日志里没有 OOM 字样, 极易误判。独立容器提交后 JM 只需管自己。
#
# 判据为什么是"集群里出现该作业名"而不是"客户端打印 succeeded":
#   实测教训 —— sql-client 对 `-i` 里的每条 DDL 也打印 "Execute statement succeeded",
#   于是"INSERT 失败但 DDL 成功"会被误判成提交成功(本次就这么被骗过一次)。
#   真正成立的事实只有一个: **集群 REST 里出现该作业**。
#
# 用法: bash warehouse/streaming/submit-jobs.sh [作业名...]     # 缺省提交全部三个
# 幂等: **不幂等** —— 重复提交会产生重复计算; 重提前先停旧作业(README"停作业"一节)。
set -uo pipefail

# 仓库根: 本脚本位于 warehouse/streaming/, 故上溯两级 —— 2026-09-20 重构时曾漏改这里,
# 结果挂载源变成 warehouse/warehouse/streaming/... , docker 直接报错但脚本仍打印 ✅(见下条修复)。
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${FLINK_IMAGE:-oceanverse/flink:1.20.5}"
NET="${FLINK_NETWORK:-oceanverse_ov-net}"
REST="${FLINK_REST:-http://127.0.0.1:18088}"
JOBS=("$@")
[ ${#JOBS[@]} -eq 0 ] && JOBS=(10-online-count 20-fault-count 30-high-temp)

# 作业名 ↔ 文件名（作业名在 SQL 文件的 SET 'pipeline.name' 里, 这里只用于回查）
# 兼容性: 本机 /bin/bash 是 3.2 —— 不支持 declare -A, 且裸 $VAR 后跟全角字符会被并进变量名
#         (两处都踩过: `online: unbound variable` / `name）: unbound variable`)。
# 注意: 用 case 而不是关联数组 —— macOS 自带 bash 3.2 **不支持 declare -A**
#       （踩过: 报 `online: unbound variable`, 因为它把 [10-online-count] 当算术表达式求值）
job_name() {
  case "$1" in
    10-online-count) echo ov-online-count-1m ;;
    20-fault-count)  echo ov-fault-count-1m ;;
    30-high-temp)    echo ov-high-temp-battery-1m ;;
    *)               echo "" ;;
  esac
}

fail=0
for job in "${JOBS[@]}"; do
  name="$(job_name "${job}")"
  [ -z "${name}" ] && { echo "  ❌ 未知作业: ${job}"; fail=1; continue; }
  printf '  %-22s ' "${job}"
  # 守卫: 同名作业**处于活动状态**时拒绝提交。**不幂等**是这套流程的固有属性(每个作业是独立流作业),
  # 重复提交会造成重复计算, 所以宁可挡住也不要"看着成功、实际算了两遍"（本次就发生过一次）。
  # 注意必须过滤状态: /jobs/overview 里**还留着已取消/已完成的历史作业** ——
  #   第一版守卫没过滤, 于是刚取消的作业也被当成"在跑", 把重提全挡了(实测踩到)。
  active=$(curl -s --max-time 5 "${REST}/jobs/overview" 2>/dev/null | python3 -c "
import json,sys
name=sys.argv[1]
try: d=json.load(sys.stdin)['jobs']
except Exception: d=[]
live={'RUNNING','CREATED','RESTARTING','RECONCILING','CANCELLING','FAILING'}
print(sum(1 for j in d if j.get('name')==name and j.get('state') in live))
" "${name}")
  if [ "${active:-0}" != "0" ]; then
    echo "⏭  已在运行（${name}）—— 先停掉再提, 避免重复计算"; continue
  fi
  out=$(docker run --rm --network "${NET}" --memory=640m \
      -v "${ROOT}/warehouse/streaming/conf/sql-client-flink-conf.yaml:/opt/flink/conf/flink-conf.yaml:ro" \
      -v "${ROOT}/warehouse/streaming/sql:/opt/flink/sql:ro" \
      "${IMAGE}" /opt/flink/bin/sql-client.sh \
      -i /opt/flink/sql/00-common.sql -f "/opt/flink/sql/${job}.sql" 2>&1 \
      | grep -viE "WARNING: Unknown module|Unable to create a system terminal|org.jline.utils.Log")

  if grep -q "\[ERROR\]" <<< "${out}"; then
    echo "❌ 客户端报错"; echo "${out}" | grep -A3 "\[ERROR\]" | tail -5 | sed 's/^/      /'; fail=1; continue
  fi
  # 客户端连"成功"都没打印 → 多半是容器/挂载本身失败(docker 的报错不走 sql-client 的 [ERROR] 格式)
  if ! grep -q "Execute statement succeeded" <<< "${out}"; then
    echo "❌ 客户端没有正常输出（容器/挂载失败?）"; echo "${out}" | tail -5 | sed 's/^/      /'; fail=1; continue
  fi
  # 强判据: 轮询集群, 直到出现**活动状态**的该作业（最多 60s）。
  # 必须过滤状态: /jobs/overview 里还留着已取消/已完成的历史作业 ——
  # 第一版回查只看名字, 于是"提交其实失败(docker 挂载源不存在)"却被历史作业匹配成 ✅(实测踩到,
  # 与守卫那次是同一个坑的两半: 守卫修了、回查没修)。
  ok=""
  for _ in $(seq 1 20); do
    live=$(curl -s --max-time 5 "${REST}/jobs/overview" 2>/dev/null | python3 -c "
import json,sys
name=sys.argv[1]
try: d=json.load(sys.stdin)['jobs']
except Exception: d=[]
live={'RUNNING','CREATED','RESTARTING','RECONCILING','CANCELLING','FAILING'}
print(sum(1 for j in d if j.get('name')==name and j.get('state') in live))
" "${name}" 2>/dev/null)
    if [ "${live:-0}" != "0" ]; then ok=1; break; fi
    sleep 3
  done
  if [ -n "${ok}" ]; then echo "✅ 已在集群中运行（${name}）"; else
    echo "❌ 提交后集群里没有活动状态的该作业"
    echo "${out}" | tail -6 | sed 's/^/      /'
    fail=1
  fi
done

echo
echo "  集群作业一览:"
curl -s --max-time 10 "${REST}/jobs/overview" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)['jobs']
except Exception:
    print('    （取不到集群状态: 确认 docker compose --profile realtime up -d 已起 Flink）'); raise SystemExit
for j in d: print(f\"    - {j['name']:26} {j['state']}\")
print(f'    共 {len(d)} 个')
"
exit ${fail}
