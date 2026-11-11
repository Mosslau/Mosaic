#!/usr/bin/env bash
# engineering 域校验：D1 契约内核（必跑）+ D0 共享底座烟测（Docker 可用时）。
# 退出码：0 全通过 / 1 有失败 / 2 无失败但 D0 被跳过。
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FAIL=0

echo "== D1 契约内核 =="
for unit in data-platform/P1-contract-kernel data-platform/P2-device-slice ai-platform/P1-contract-kernel ai-platform/P2-fault-rag; do
  echo "-- $unit"
  (cd "$unit" && ./test.sh >/tmp/mosaic-d1-$(basename "$unit").log 2>&1)
  code=$?
  if [ "$code" -eq 0 ]; then
    tail -1 "/tmp/mosaic-d1-$(basename "$unit").log" | sed 's/^/   /'
    echo "   ✅ $(basename "$unit") 测试通过"
  else
    echo "   ❌ $(basename "$unit") 测试失败（日志 /tmp/mosaic-d1-$(basename "$unit").log）"
    FAIL=1
  fi
done

echo "== D0 共享底座 =="
if docker info >/dev/null 2>&1; then
  (cd infra/compose && ./smoke.sh)
  [ $? -eq 0 ] || FAIL=1
else
  echo "   ⚠️  Docker daemon 不可用，D0 烟测跳过（不算通过）"
  [ "$FAIL" -eq 0 ] && exit 2
fi

[ "$FAIL" -eq 0 ] || exit 1
exit 0
