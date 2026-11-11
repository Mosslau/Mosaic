#!/usr/bin/env bash
# 诊断结果查询：答案 / 工单 / 反馈 / 账本。
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
COMPOSE="docker compose -f ../../infra/compose/docker-compose.yml"
run() { $COMPOSE exec -T postgres psql -U mosaic -d mosaic -c "$1"; }
echo "== 表行数 =="
run "select 'diagnosis_answers' as table, count(*) from diagnosis_answers union all select 'workorders', count(*) from workorders union all select 'feedback_events', count(*) from feedback_events union all select 'ai_pipeline_ledger', count(*) from ai_pipeline_ledger;"
echo "== 诊断答案（最近 5 条） =="
run "select fault_code, confidence, no_evidence, coalesce(citations->0->>'locator','-') as citation from diagnosis_answers order by created_at desc limit 5;"
echo "== 工单（最近 5 条） =="
run "select workorder_id, action_type, status from workorders order by created_at desc limit 5;"
echo "== 反馈分布 =="
run "select verdict, reason_code, count(*) from feedback_events group by 1,2 order by 1;"
echo "== 最近一次 AI 纵切账本 =="
run "select stage, detail from ai_pipeline_ledger where trace_id = (select trace_id from ai_pipeline_ledger order by id desc limit 1) order by id;"
