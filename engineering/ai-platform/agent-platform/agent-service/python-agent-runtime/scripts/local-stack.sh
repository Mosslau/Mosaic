#!/usr/bin/env bash
# 本地一键启动/停止 data-agent Python Runtime 联调栈。
#
# 管理以下进程：
#   1. examples/test_mcp_server.py：测试 MCP + 测试 RAG，端口 8810；
#   2. data-agent-runtime：Runtime API，默认端口 8800；
#   3. data-agent-worker：Redis Stream Agent Worker；
#   4. python3 -m http.server：本地前端静态文件服务，默认端口 5500。
#
# 用法：
#   ./scripts/local-stack.sh start
#   ./scripts/local-stack.sh stop
#   ./scripts/local-stack.sh restart
#   ./scripts/local-stack.sh status
#   ./scripts/local-stack.sh logs

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${DATA_AGENT_ENV_FILE:-${PROJECT_ROOT}/.env}"
if [[ "${ENV_FILE}" != /* ]]; then
  ENV_FILE="${PROJECT_ROOT}/${ENV_FILE}"
fi
export DATA_AGENT_ENV_FILE="${ENV_FILE}"
RUNTIME_DIR="${PROJECT_ROOT}/.local"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${RUNTIME_DIR}/logs"

# uv 默认缓存目录在部分受限环境中可能没有写权限，允许调用方覆盖。
export UV_CACHE_DIR="${UV_CACHE_DIR:-${PROJECT_ROOT}/.uv-cache}"

MCP_HOST="${TEST_MCP_HOST:-127.0.0.1}"
MCP_PORT="${TEST_MCP_PORT:-8810}"
API_HOST="${RUNTIME_HOST:-127.0.0.1}"
API_PORT="${RUNTIME_PORT:-8800}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-5500}"

# 从 .env 中读取简单的 KEY=value 配置；这里只用于读取端口，不会 source 整个 .env。
read_env_value() {
  local key="$1"
  if [[ ! -f "${ENV_FILE}" ]]; then
    return 0
  fi
  sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "${ENV_FILE}" \
    | tail -n 1 \
    || true
}

if [[ -f "${ENV_FILE}" ]]; then
  API_PORT="${RUNTIME_PORT:-$(read_env_value PORT)}"
  API_PORT="${API_PORT:-8800}"
fi

# 无论从哪个目录调用脚本，都在项目根目录执行 uv 和相对路径命令。
# 这样可以直接运行：/path/to/python-agent-runtime/scripts/local-stack.sh start
cd "${PROJECT_ROOT}"

mkdir -p "${PID_DIR}" "${LOG_DIR}"

log() {
  printf '[local-stack] %s\n' "$*"
}

warn() {
  printf '[local-stack][WARN] %s\n' "$*" >&2
}

fail() {
  printf '[local-stack][ERROR] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "找不到命令：$1，请先安装或加入 PATH。"
}

pid_file() {
  printf '%s/%s.pid' "${PID_DIR}" "$1"
}

log_file() {
  printf '%s/%s.log' "${LOG_DIR}" "$1"
}

read_pid() {
  local name="$1"
  local file
  file="$(pid_file "${name}")"
  [[ -f "${file}" ]] || return 1
  tr -d '[:space:]' <"${file}"
}

process_alive() {
  local pid="$1"
  [[ "${pid}" =~ ^[0-9]+$ ]] || return 1
  kill -0 "${pid}" >/dev/null 2>&1
}

process_command() {
  local pid="$1"
  ps -p "${pid}" -o command= 2>/dev/null || true
}

listener_pid() {
  local port="$1"
  lsof -nP -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | sed -n '1p' || true
}

matching_process_pid() {
  local name="$1"
  local pid command_line
  while read -r pid command_line; do
    [[ -n "${pid}" && "${pid}" != "$$" ]] || continue
    if expected_process "${name}" "${command_line}"; then
      printf '%s' "${pid}"
      return 0
    fi
  done < <(ps -axo pid=,command= 2>/dev/null)
  return 1
}

expected_process() {
  local name="$1"
  local command_line="$2"
  case "${name}" in
    test-mcp) [[ "${command_line}" == *"test_mcp_server.py"* ]] ;;
    api) [[ "${command_line}" == *"data-agent-runtime"* || "${command_line}" == *"data_agent_runtime.main"* || "${command_line}" == *"data_agent_runtime.api"* ]] ;;
    worker) [[ "${command_line}" == *"data-agent-worker"* || "${command_line}" == *"data_agent_runtime.worker_main"* || "${command_line}" == *"worker_main"* ]] ;;
    web) [[ "${command_line}" == *"http.server"* && "${command_line}" == *"${PROJECT_ROOT}"* ]] ;;
    *) return 1 ;;
  esac
}

service_port() {
  local name="$1"
  case "${name}" in
    test-mcp) printf '%s' "${MCP_PORT}" ;;
    api) printf '%s' "${API_PORT}" ;;
    web) printf '%s' "${WEB_PORT}" ;;
    worker) printf '' ;;
    *) return 1 ;;
  esac
}

discover_expected_pid() {
  local name="$1"
  local port candidate command_line
  port="$(service_port "${name}")"
  if [[ -n "${port}" ]]; then
    candidate="$(listener_pid "${port}")"
    [[ -n "${candidate}" ]] || return 1
    command_line="$(process_command "${candidate}")"
    expected_process "${name}" "${command_line}" || return 1
    printf '%s' "${candidate}"
    return 0
  fi
  matching_process_pid "${name}"
}

running_pid() {
  local name="$1"
  local pid
  pid="$(read_pid "${name}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    return 1
  fi
  if ! process_alive "${pid}"; then
    rm -f "$(pid_file "${name}")"
    return 1
  fi
  local command_line
  command_line="$(process_command "${pid}")"
  if ! expected_process "${name}" "${command_line}"; then
    warn "${name} 的 PID 文件指向了其他进程（PID=${pid}），不会操作该进程。"
    return 1
  fi
  printf '%s' "${pid}"
}

start_process() {
  local name="$1"
  local log_path="$2"
  local port="$3"
  shift 3

  local existing_pid
  existing_pid="$(running_pid "${name}" 2>/dev/null || true)"
  if [[ -n "${existing_pid}" ]]; then
    log "${name} 已运行（PID=${existing_pid}）。"
    return 0
  fi

  # PID 文件可能因终端关闭、脚本中断或手工启动而丢失；启动前识别同类进程。
  existing_pid="$(discover_expected_pid "${name}" 2>/dev/null || true)"
  if [[ -n "${existing_pid}" ]]; then
    printf '%s\n' "${existing_pid}" >"$(pid_file "${name}")"
    log "${name} 已运行（PID=${existing_pid}），已接管现有进程。"
    return 0
  fi

  # 启动前检查监听端口。如果端口被其他进程占用，立即失败，而不是启动子进程后
  # 再误判为成功。
  # 如果端口上的确是同一类服务，则接管它并补写 PID 文件，避免重复绑定；
  # 如果端口被其他进程占用，则明确失败，而不是启动子进程后再误判为成功。
  if [[ -n "${port}" ]]; then
    local port_pid port_command
    port_pid="$(listener_pid "${port}")"
    if [[ -n "${port_pid}" ]]; then
      port_command="$(process_command "${port_pid}")"
      if expected_process "${name}" "${port_command}"; then
        printf '%s\n' "${port_pid}" >"$(pid_file "${name}")"
        log "${name} 已在端口 ${port} 运行（PID=${port_pid}），已接管现有进程。"
        return 0
      fi
      fail "${name} 所需端口 ${port} 已被其他进程占用（PID=${port_pid}）。请先停止该进程，或设置其他端口。"
    fi
  fi

  log "启动 ${name}..."
  : >"${log_path}"
  nohup "$@" >"${log_path}" 2>&1 </dev/null &
  local pid=$!
  printf '%s\n' "${pid}" >"$(pid_file "${name}")"
  sleep 0.5

  if ! process_alive "${pid}"; then
    warn "${name} 启动失败，日志：${log_path}"
    tail -n 30 "${log_path}" >&2 || true
    rm -f "$(pid_file "${name}")"
    return 1
  fi

  log "${name} 已启动（PID=${pid}，日志=${log_path}）。"
}

stop_process() {
  local name="$1"
  local pid
  pid="$(running_pid "${name}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    # 即使 PID 文件丢失，也尝试识别同类监听进程或 Worker，避免 stop 误报未运行。
    pid="$(discover_expected_pid "${name}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]]; then
      log "${name} 发现未登记的现有进程（PID=${pid}），准备停止。"
    fi
  fi
  if [[ -z "${pid}" ]]; then
    rm -f "$(pid_file "${name}")"
    log "${name} 未运行。"
    return 0
  fi

  log "停止 ${name}（PID=${pid}）..."
  kill -TERM "${pid}" >/dev/null 2>&1 || true

  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if ! process_alive "${pid}"; then
      rm -f "$(pid_file "${name}")"
      log "${name} 已停止。"
      return 0
    fi
    sleep 0.5
  done

  warn "${name} 未在 5 秒内退出，发送 SIGKILL。"
  kill -KILL "${pid}" >/dev/null 2>&1 || true
  rm -f "$(pid_file "${name}")"
}

wait_for_port() {
  local name="$1"
  local host="$2"
  local port="$3"
  local attempts="${4:-30}"
  local i

  require_command lsof
  for ((i = 1; i <= attempts; i++)); do
    if lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | grep -q "LISTEN"; then
      log "${name} 已监听 ${host}:${port}。"
      return 0
    fi
    sleep 1
  done

  warn "等待 ${name} 监听 ${host}:${port} 超时。"
  return 1
}

wait_for_api() {
  local attempts="${1:-30}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS --max-time 2 "http://${API_HOST}:${API_PORT}/v1/health" >/dev/null 2>&1; then
      log "Runtime API 健康检查通过：http://${API_HOST}:${API_PORT}/v1/health"
      return 0
    fi
    sleep 1
  done
  warn "Runtime API 健康检查超时，日志：$(log_file api)"
  return 1
}

check_prerequisites() {
  require_command uv
  require_command python3
  require_command curl
  require_command lsof
  [[ -f "${ENV_FILE}" ]] || fail "没有找到 ${ENV_FILE}，请先创建 .env。"
  [[ -f "${PROJECT_ROOT}/examples/run.json" ]] || fail "没有找到 examples/run.json。"
  [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]] || warn "没有检测到 .venv；uv run 会按项目配置自动准备虚拟环境。"
}

show_status() {
  printf '%-12s %-8s %s\n' "SERVICE" "PID" "STATUS"
  printf '%-12s %-8s %s\n' "-------" "---" "------"
  local name pid command_line
  for name in test-mcp api worker web; do
    pid="$(running_pid "${name}" 2>/dev/null || true)"
    if [[ -z "${pid}" ]]; then
      pid="$(discover_expected_pid "${name}" 2>/dev/null || true)"
    fi
    if [[ -n "${pid}" ]]; then
      command_line="$(process_command "${pid}")"
      printf '%-12s %-8s %s\n' "${name}" "${pid}" "RUNNING"
      [[ -n "${command_line}" ]] || true
    else
      printf '%-12s %-8s %s\n' "${name}" "-" "STOPPED"
    fi
  done
  printf '\n日志目录：%s\n' "${LOG_DIR}"
}

show_logs() {
  log "日志目录：${LOG_DIR}"
  ls -lh "${LOG_DIR}" 2>/dev/null || true
  printf '\n查看单个日志示例：\n  tail -f %s\n' "$(log_file worker)"
}

start_stack() {
  check_prerequisites

  start_process \
    test-mcp "$(log_file test-mcp)" "${MCP_PORT}" \
    uv run python examples/test_mcp_server.py \
    --host "${MCP_HOST}" --port "${MCP_PORT}"
  wait_for_port "测试 MCP/RAG" "${MCP_HOST}" "${MCP_PORT}" || {
    stop_process test-mcp
    fail "测试 MCP/RAG 启动失败，请查看 $(log_file test-mcp)。"
  }

  start_process \
    api "$(log_file api)" "${API_PORT}" \
    env RUNTIME_MODE=api uv run data-agent-runtime
  wait_for_api || {
    stop_process api
    stop_process test-mcp
    tail -n 50 "$(log_file api)" >&2 || true
    fail "Runtime API 启动失败，请检查 Redis、PostgreSQL 和 .env。"
  }

  start_process \
    worker "$(log_file worker)" "" \
    env RUNTIME_MODE=worker uv run data-agent-worker
  sleep 1
  if [[ -z "$(running_pid worker 2>/dev/null || true)" ]]; then
    stop_process api
    stop_process test-mcp
    tail -n 50 "$(log_file worker)" >&2 || true
    fail "Agent Worker 启动失败，请检查 $(log_file worker)。"
  fi

  start_process \
    web "$(log_file web)" "${WEB_PORT}" \
    python3 -m http.server "${WEB_PORT}" \
    --bind "${WEB_HOST}" \
    --directory "${PROJECT_ROOT}/examples"
  wait_for_port "前端静态服务" "${WEB_HOST}" "${WEB_PORT}" || {
    stop_process web
    stop_process worker
    stop_process api
    stop_process test-mcp
    fail "前端静态服务启动失败，请检查端口 ${WEB_PORT}。"
  }

  printf '\n'
  log "本地联调栈启动完成。"
  printf '  测试 MCP/RAG：http://%s:%s/mcp\n' "${MCP_HOST}" "${MCP_PORT}"
  printf '  Runtime API ：http://%s:%s\n' "${API_HOST}" "${API_PORT}"
  printf '  健康检查    ：http://%s:%s/v1/health\n' "${API_HOST}" "${API_PORT}"
  printf '  前端页面    ：http://%s:%s/agent-chat-runtime.html\n' "${WEB_HOST}" "${WEB_PORT}"
  printf '  日志目录    ：%s\n' "${LOG_DIR}"
  printf '\n停止全部服务：\n  ./scripts/local-stack.sh stop\n'
}

stop_stack() {
  # 反向停止，先停止前端和 Worker，再停止 API 和测试 MCP。
  stop_process web
  stop_process worker
  stop_process api
  stop_process test-mcp
  log "本地联调栈已停止。"
}

usage() {
  cat <<EOF
用法：$0 <command>

command:
  start    启动测试 MCP/RAG、Runtime API、Worker 和前端
  stop     停止本脚本启动的全部服务
  restart  先停止，再启动
  status   查看服务状态
  logs     查看日志目录
EOF
}

command="${1:-}"
case "${command}" in
  start)
    start_stack
    ;;
  stop)
    stop_stack
    ;;
  restart)
    stop_stack
    start_stack
    ;;
  status)
    show_status
    ;;
  logs)
    show_logs
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
