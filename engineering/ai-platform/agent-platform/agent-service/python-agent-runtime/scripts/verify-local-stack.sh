#!/usr/bin/env bash
# 本地联调栈端到端验证入口。
#
# 默认使用项目根目录 .env，启动 API、Worker、测试 MCP 和前端后，调用
# scripts/verify-local-stack.py 验证完整链路。脚本不会 source .env，避免把配置
# 文件中的任意内容当作 Shell 命令执行；local-stack.sh 和 Pydantic Settings 会显式读取它。
#
# 用法：
#   ./scripts/verify-local-stack.sh                  # 启动并完整验证，结束后停止本次栈
#   ./scripts/verify-local-stack.sh --keep           # 验证完成后保留服务
#   ./scripts/verify-local-stack.sh --no-start       # 不启动，验证已运行的服务
#   ./scripts/verify-local-stack.sh --smoke          # 不执行真实模型 Run
#   DATA_AGENT_ENV_FILE=.env.prod ./scripts/verify-local-stack.sh --no-start

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${DATA_AGENT_ENV_FILE:-${PROJECT_ROOT}/.env}"
if [[ "${ENV_FILE}" != /* ]]; then
  ENV_FILE="${PROJECT_ROOT}/${ENV_FILE}"
fi
ENV_FILE="$(cd -- "$(dirname -- "${ENV_FILE}")" && pwd)/$(basename -- "${ENV_FILE}")"

KEEP=0
NO_START=0
PYTHON_ARGS=()
for arg in "$@"; do
  case "${arg}" in
    --keep)
      KEEP=1
      ;;
    --no-start)
      NO_START=1
      ;;
    --help|-h)
      cat <<EOF
用法：$0 [--keep] [--no-start] [--smoke] [验证器参数]

默认使用 .env，启动本地联调栈并验证完整 Runtime 链路；验证结束后停止本次启动的服务。
  --keep       验证结束后保留 API、Worker、MCP 和 Web 服务
  --no-start   不启动服务，只验证已经运行的本地联调栈
  --smoke      跳过真实模型 Run，只验证健康、鉴权和资源接口
  --run-timeout N  等待 Worker 完成 Run 的最长秒数，默认 180
  --allow-run-failure 允许 Run 进入 FAILED/CANCELLED 后继续验证事件和幂等链路
EOF
      exit 0
      ;;
    *)
      # 其他参数全部透传给 Python 验证器；带值参数的下一项也会原样透传。
      PYTHON_ARGS+=("${arg}")
      ;;
  esac
done

fail() {
  printf '[verify-e2e][ERROR] %s\n' "$*" >&2
  exit 1
}

[[ -f "${ENV_FILE}" ]] || fail "没有找到配置文件 ${ENV_FILE}。请先准备 .env。"
command -v uv >/dev/null 2>&1 || fail "找不到 uv。"
command -v curl >/dev/null 2>&1 || fail "找不到 curl。"

cd "${PROJECT_ROOT}"
export DATA_AGENT_ENV_FILE="${ENV_FILE}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${PROJECT_ROOT}/.uv-cache}"

all_services_running() {
  local output
  output="$(./scripts/local-stack.sh status 2>/dev/null || true)"
  grep -qE '^test-mcp[[:space:]].*RUNNING' <<<"${output}" \
    && grep -qE '^api[[:space:]].*RUNNING' <<<"${output}" \
    && grep -qE '^worker[[:space:]].*RUNNING' <<<"${output}" \
    && grep -qE '^web[[:space:]].*RUNNING' <<<"${output}"
}

started_stack=0
had_complete_stack=0
had_any_service=0
if all_services_running; then
  had_complete_stack=1
fi
if ./scripts/local-stack.sh status 2>/dev/null | grep -qE '^((test-mcp|api|worker|web)[[:space:]].*RUNNING)'; then
  had_any_service=1
fi

cleanup() {
  local status=$?
  if [[ "${KEEP}" -eq 0 && "${NO_START}" -eq 0 && "${started_stack}" -eq 1 && "${had_complete_stack}" -eq 0 && "${had_any_service}" -eq 0 ]]; then
    printf '[verify-e2e] 停止本次启动的本地联调栈。\n'
    ./scripts/local-stack.sh stop >/dev/null 2>&1 || true
  elif [[ "${KEEP}" -eq 1 ]]; then
    printf '[verify-e2e] 按 --keep 保留本地联调栈。\n'
  fi
  exit "${status}"
}
trap cleanup EXIT INT TERM

if [[ "${NO_START}" -eq 0 ]]; then
  printf '[verify-e2e] 使用配置文件：%s\n' "${ENV_FILE}"
  ./scripts/local-stack.sh start
  started_stack=1
else
  printf '[verify-e2e] 使用已运行的本地联调栈，不启动新进程。\n'
fi

verify_command=(
  env
  "DATA_AGENT_ENV_FILE=${ENV_FILE}"
  "UV_CACHE_DIR=${UV_CACHE_DIR}"
  uv run python scripts/verify-local-stack.py
  --env-file "${ENV_FILE}"
)
if (( ${#PYTHON_ARGS[@]} > 0 )); then
  verify_command+=("${PYTHON_ARGS[@]}")
fi

set +e
"${verify_command[@]}"
verify_status=$?
set -e
exit "${verify_status}"
