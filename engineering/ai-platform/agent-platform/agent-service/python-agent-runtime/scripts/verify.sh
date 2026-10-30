#!/usr/bin/env bash
# 运行 Python Runtime 的本地验证：单元测试、静态检查和可选 Redis P0 集成测试。
#
# 用法：
#   ./scripts/verify.sh
#   P0_TEST_REDIS_URL='redis://:password@127.0.0.1:6379/15' ./scripts/verify.sh --p0
#
# 默认不会连接开发 Redis；只有显式传入 --p0 且设置 P0_TEST_REDIS_URL 时才运行
# Pending reclaim、Lease、Session 串行、重试和死信等真实 Redis 测试。

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

PYTHON="${PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3 || true)"
fi
[[ -n "${PYTHON}" && -x "${PYTHON}" ]] || {
  echo "[verify][ERROR] 找不到 Python，请先创建 .venv 或设置 PYTHON。" >&2
  exit 1
}

run() {
  printf '[verify] %s\n' "$*"
  "$@"
}

run "${PYTHON}" -m pytest -q
run "${PYTHON}" -m ruff check src tests
run "${PYTHON}" scripts/check_docstrings.py
run git diff --check

if [[ "${1:-}" == "--p0" ]]; then
  if [[ -z "${P0_TEST_REDIS_URL:-}" ]]; then
    echo "[verify][ERROR] --p0 需要设置 P0_TEST_REDIS_URL。" >&2
    exit 2
  fi
  run env P0_TEST_REDIS_URL="${P0_TEST_REDIS_URL}" "${PYTHON}" -m pytest -q tests/test_p0_reliability.py
else
  echo "[verify] 未运行 P0 Redis 集成测试；如需运行请设置 P0_TEST_REDIS_URL 并传入 --p0。"
fi

echo "[verify] 验证完成。"
