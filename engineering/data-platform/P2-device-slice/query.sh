#!/usr/bin/env bash
# 纵切结果查询：长表 / 故障 / 账本 / 版本分布。
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
COMPOSE="docker compose -f ../../infra/compose/docker-compose.yml"
run() { $COMPOSE exec -T postgres psql -U mosaic -d mosaic -c "$1"; }
echo "== 表行数 =="
run "select 'signal_long' as table, count(*) from signal_long union all select 'fault_events', count(*) from fault_events union all select 'pipeline_ledger', count(*) from pipeline_ledger;"
echo "== 故障事件 =="
run "select device_id, fault_code, severity, ts, value from fault_events order by ts desc limit 10;"
echo "== 协议版本分布 =="
run "select protocol_version, codec_version, count(*) from signal_long group by 1,2 order by 1;"
echo "== 最近一次纵切的账本 =="
run "select stage, detail from pipeline_ledger where trace_id = (select trace_id from pipeline_ledger order by id desc limit 1) order by id;"
