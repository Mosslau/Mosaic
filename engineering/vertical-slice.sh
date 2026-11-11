#!/usr/bin/env bash
# 一条命令跑通跨平台纵切：设备帧 → 数据平台 → 故障 → AI 诊断 → 工单 → 反馈。
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
COMPOSE="docker compose -f infra/compose/docker-compose.yml"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 不可用：先起 Docker" >&2
  exit 1
fi
if ! $COMPOSE ps --services --filter status=running 2>/dev/null | grep -qx kafka; then
  echo "共享底座没起：先执行 ./infra/compose/up.sh" >&2
  exit 1
fi

echo "== 1/3 数据侧：设备帧 → Kafka → 解码 → 长表 / 故障 =="
./data-platform/P2-device-slice/slice.sh

echo
echo "== 2/3 AI 侧：故障 → 检索 → 带引用答案 → 工单 → 反馈 =="
./ai-platform/P2-fault-rag/rag.sh --limit 20

echo
echo "== 3/3 闭环结果 =="
$COMPOSE exec -T postgres psql -U mosaic -d mosaic -c "
select 'fault_events' as table, count(*) from fault_events
union all select 'diagnosis_answers', count(*) from diagnosis_answers
union all select 'workorders', count(*) from workorders
union all select 'feedback_events', count(*) from feedback_events;"
