#!/usr/bin/env bash
# submit-jobs.sh — 把 lakehouse/warehouse/streaming/sql/ 下的三个 Flink SQL 作业提交到 session cluster
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
# 用法: bash lakehouse/warehouse/streaming/submit-jobs.sh [作业名...]     # 缺省提交全部三个
# 幂等: **不幂等** —— 重复提交会产生重复计算; 重提前先停旧作业(README"停作业"一节)。
set -uo pipefail

# 仓库根: 本脚本位于 lakehouse/warehouse/streaming/, 故上溯**三级**。
# ⚠️ 这个变量已经因目录重构错过一次(2026-09-20): 脚本深了一层而这里没跟着改, 挂载源变成不存在的路径,
#    docker 直接报错, 但脚本当时仍打印 ✅(假成功)。**改目录层级时必须一起看这里**。
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
IMAGE="${FLINK_IMAGE:-oceanverse/flink:1.20.5}"
NET="${FLINK_NETWORK:-oceanverse_ov-net}"
REST="${FLINK_REST:-http://127.0.0.1:18088}"
# 作业专属 SQL 的暂存目录（占位符替换后挂进提交容器; .tmp-* 已在 .gitignore）
STAGE="${ROOT}/.tmp-realtime-submit"
JOBS=("$@")

# ---- 提交端配置: 作业级配置的**唯一生效来源** ----------------------------------------
# 实测(2026-09-20): 只把 `execution.checkpointing.interval: 60s` 写在 deploy/docker-compose.yaml
# 的 JM/TM 上, 作业跑满 3 分钟 /jobs/:jid/checkpoints 仍是 total=0(failed=0/in_progress=0) ——
# **SQL Client 不会把远端集群的作业级配置注入 JobGraph**, 作业的 ExecutionConfig 全部来自提交端。
# 所以检查点/重启策略/S3 客户端必须在这里给全, compose 里那份只是集群默认值。
# 与 compose 同名的键由 scripts/check-docs.sh ⑩ 逐条比对(值不一致 → CI 红, 防两处漂移)。
# ⚠ 块内只能有 `key: value`: 官方入口把 FLINK_PROPERTIES 当 YAML 解析后**写回**容器内
#   conf/config.yaml, 注释行也会变成配置键(见 compose 里同一条说明)。
CLIENT_FLINK_PROPERTIES="rest.address: flink-jobmanager
rest.port: 8081
env.java.opts.client: -Xmx256m
execution.checkpointing.dir: s3://oceanverse-flink/checkpoints
execution.checkpointing.savepoint-dir: s3://oceanverse-flink/savepoints
execution.checkpointing.interval: 60s
execution.checkpointing.min-pause: 30s
execution.checkpointing.timeout: 5min
restart-strategy: fixed-delay
restart-strategy.fixed-delay.attempts: 3
restart-strategy.fixed-delay.delay: 10s
s3.endpoint: http://minio:9000
s3.path.style.access: true
s3.access-key: ov_minio
s3.secret-key: ov_minio_2026"
[ ${#JOBS[@]} -eq 0 ] && JOBS=(10-online-count 20-fault-count 30-high-temp)

# 作业名 ↔ 文件名（作业名在 SQL 文件的 SET 'pipeline.name' 里, 这里只用于回查）
# 兼容性: 本机 /bin/bash 是 3.2 —— 不支持 declare -A, 且裸 $VAR 后跟全角字符会被并进变量名
#         (两处都踩过: `online: unbound variable` / `name）: unbound variable`)。
# 注意: 用 case 而不是关联数组 —— macOS 自带 bash 3.2 **不支持 declare -A**
#       （踩过: 报 `online: unbound variable`, 因为它把 [10-online-count] 当算术表达式求值）
# 作业 → 独立消费组。**必须一作业一组**: 共用时 Kafka 会把分区瓜分给不同作业, 指标静默变成 1/3。
# 作业 → sink 事务前缀（`sink.delivery-guarantee=exactly-once` 要求**每个作业唯一**,
# 否则两个作业的事务会互相覆盖）。与消费组同源命名。
job_txn_prefix() {
  case "$1" in
    10-online-count) echo oceanverse-online-1m ;;
    20-fault-count)  echo oceanverse-fault-1m ;;
    30-high-temp)    echo oceanverse-hightemp-1m ;;
    *)               echo "" ;;
  esac
}

job_group() {
  case "$1" in
    10-online-count) echo flink-realtime-online-1m ;;
    20-fault-count)  echo flink-realtime-fault-1m ;;
    30-high-temp)    echo flink-realtime-hightemp-1m ;;
    *)               echo "" ;;
  esac
}

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
  # 生成作业专属 SQL: 把 __JOB_GROUP_ID__ 换成该作业的消费组（Flink SQL Client 不支持 ${VAR}, 故在脚本侧替换）
  gid="$(job_group "${job}")"
  rm -rf "${STAGE}"; mkdir -p "${STAGE}"
  txn="$(job_txn_prefix "${job}")"
  sed -e "s/__JOB_GROUP_ID__/${gid}/" -e "s/__JOB_TXN_PREFIX__/${txn}/" \
      "${ROOT}/lakehouse/warehouse/streaming/sql/00-common.sql" > "${STAGE}/00-common.sql"
  # 占位符必须**全部**替换掉: 漏一个就会以字面量提交(Flink 会当成合法名字, 静默出错)
  if grep -q '__JOB_' "${STAGE}/00-common.sql"; then
    echo "❌ 占位符替换失败: $(grep -o '__JOB_[A-Z_]*__' "${STAGE}/00-common.sql" | sort -u | tr '\n' ' ')"; fail=1; continue
  fi
  cp "${ROOT}/lakehouse/warehouse/streaming/sql/${job}.sql" "${STAGE}/${job}.sql"
  # 客户端如何找到远端集群: 用 FLINK_PROPERTIES 环境变量 —— 官方入口把它合并进容器内的
  # conf/config.yaml(1.20 的配置文件名, 不是 flink-conf.yaml)。**不要**把 conf 文件以 :ro 挂进去:
  # 入口的 prepare_configuration 需要**写回**该文件, 只读挂载会让它报
  # `config.yaml: Read-only file system`, 症状是"DDL 初始化失败"而不是挂载报错(实测踩到)。
  out=$(docker run --rm --network "${NET}" --memory=640m \
      -e "FLINK_PROPERTIES=${CLIENT_FLINK_PROPERTIES}" \
      -v "${STAGE}:/opt/flink/sql:ro" \
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

rm -rf "${STAGE}"

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
