#!/usr/bin/env bash
# D0 验收烟测：组件健康 + dummy 链路（Kafka → PG → Redis）+ 观测入口 + MinIO/Vault。
# 通过标准对应 V0-1/V0-2/A0-1/A0-2 的最小证据；7 个组件任一不可用即失败。
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PASS=0
FAIL=0
ok()  { printf '  \033[32m✅\033[0m %s\n' "$1"; PASS=$((PASS + 1)); }
bad() { printf '  \033[31m❌\033[0m %s\n' "$1"; FAIL=$((FAIL + 1)); }

echo "== 1. 容器状态 =="
docker compose ps --format '  {{.Name}}\t{{.Status}}'

echo
echo "== 2. Kafka：建 topic + 生产/消费一条 =="
if docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic mosaic.smoke --partitions 1 --replication-factor 1 >/dev/null 2>&1; then
  printf 'hello-mosaic\n' | docker compose exec -T kafka \
    /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:9092 \
    --topic mosaic.smoke >/dev/null 2>&1
  MSG=$(docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 --topic mosaic.smoke --from-beginning \
    --max-messages 1 --timeout-ms 20000 2>/dev/null | tr -d '\r' | head -1)
  if [ "${MSG}" = "hello-mosaic" ]; then
    ok "topic mosaic.smoke 可写可读（${MSG}）"
  else
    bad "Kafka 消费结果不符：'${MSG}'"
  fi
else
  bad "Kafka topic 创建失败"
fi

echo
echo "== 3. Postgres：建表 / 写入 / 查询 =="
if docker compose exec -T postgres psql -U mosaic -d mosaic -v ON_ERROR_STOP=1 -q \
  -c "drop table if exists d0_smoke" \
  -c "create table d0_smoke (id serial primary key, note text not null, created_at timestamptz default now())" >/dev/null 2>&1; then
  docker compose exec -T postgres psql -U mosaic -d mosaic -v ON_ERROR_STOP=1 -q \
    -c "insert into d0_smoke(note) values ('d0-smoke')" >/dev/null 2>&1
  CNT=$(docker compose exec -T postgres psql -U mosaic -d mosaic -tAc \
    "select count(*) from d0_smoke where note='d0-smoke'" 2>/dev/null | tr -d ' \r')
  if [ "${CNT:-0}" -ge 1 ]; then
    ok "d0_smoke 写入并查到 ${CNT} 行"
  else
    bad "d0_smoke 查询为空"
  fi
else
  bad "Postgres 建表失败"
fi

echo
echo "== 4. Redis：set / get =="
docker compose exec -T redis redis-cli set d0:smoke ok >/dev/null 2>&1
VAL=$(docker compose exec -T redis redis-cli get d0:smoke 2>/dev/null | tr -d '\r')
if [ "${VAL}" = "ok" ]; then
  ok "redis d0:smoke=${VAL}"
else
  bad "redis get 结果不符：'${VAL}'"
fi

echo
echo "== 5. Prometheus / Grafana =="
if curl -fsS --max-time 5 http://localhost:19090/-/healthy >/dev/null 2>&1; then
  ok "Prometheus :19090 healthy"
else
  bad "Prometheus :19090 不可用"
fi
if curl -fsS --max-time 5 'http://localhost:19090/api/v1/query?query=up' 2>/dev/null | grep -q '"status":"success"'; then
  ok "Prometheus 查询 API 返回 success"
else
  bad "Prometheus 查询 API 失败"
fi
if curl -fsS --max-time 5 http://localhost:13000/api/health 2>/dev/null | grep -q '"database": *"ok"'; then
  ok "Grafana :13000 health=ok"
else
  bad "Grafana :13000 不可用"
fi
if [ -n "$(docker compose logs --tail=3 kafka 2>/dev/null)" ]; then
  ok "容器日志可查（docker compose logs kafka）"
else
  bad "容器日志不可读"
fi

echo
echo "== 6. MinIO：健康 + 建桶/写读对象 =="
if curl -fsS --max-time 5 http://localhost:19000/minio/health/live >/dev/null 2>&1; then
  ok "MinIO :19000 health=live"
else
  bad "MinIO :19000 不可用"
fi
MC=(docker compose exec -T minio mc --config-dir /tmp/.mc)
if "${MC[@]}" alias set local http://localhost:9000 mosaic mosaic123 >/dev/null 2>&1; then
  "${MC[@]}" mb --ignore-existing local/mosaic-smoke >/dev/null 2>&1
  printf 'hello-minio\n' | "${MC[@]}" pipe local/mosaic-smoke/d0.txt >/dev/null 2>&1
  OBJ=$("${MC[@]}" cat local/mosaic-smoke/d0.txt 2>/dev/null | tr -d '\r' | head -1)
  if [ "${OBJ}" = "hello-minio" ]; then
    ok "mosaic-smoke/d0.txt 可写可读（${OBJ}）"
  else
    bad "MinIO 对象读取不符：'${OBJ}'"
  fi
else
  bad "MinIO mc alias 配置失败"
fi

echo
echo "== 7. Vault：状态 + 写读一个 secret =="
if docker compose exec -T -e VAULT_TOKEN=root vault vault status >/dev/null 2>&1; then
  ok "vault status 可读（dev 模式 unsealed）"
else
  bad "vault status 失败"
fi
docker compose exec -T -e VAULT_TOKEN=root vault vault kv put secret/d0 smoke=ok >/dev/null 2>&1
VSEC=$(docker compose exec -T -e VAULT_TOKEN=root vault vault kv get -field=smoke secret/d0 2>/dev/null | tr -d '\r')
if [ "${VSEC}" = "ok" ]; then
  ok "secret/d0 smoke=${VSEC} 可写可读"
else
  bad "Vault secret 读取不符：'${VSEC}'"
fi

echo
echo "== 汇总 =="
echo "  通过 ${PASS} 项，失败 ${FAIL} 项"
if [ "${FAIL}" -gt 0 ]; then
  echo "  结论：D0 未通过"
  exit 1
fi
echo "  结论：D0 通过（7 个组件全部健康）"
