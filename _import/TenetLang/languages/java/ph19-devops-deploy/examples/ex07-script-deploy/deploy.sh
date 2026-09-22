#!/usr/bin/env bash
# examples/ex07-script-deploy/deploy.sh —— systemd 托管 Java 服务的部署/生命周期脚本（对应主文档 3.1）
# 教学点：
#   1. set -euo pipefail：出错即停 / 未定义变量报错 / 管道失败暴露 —— 现代 bash 的安全默认
#   2. 探活走 HTTP 而非「进程在不在」：进程活着不等于服务可用（呼应 readiness 语义）
#   3. 停服务用 SIGTERM 走优雅停机（Spring server.shutdown=graceful），再给超时窗口
# 面向环境：Linux（systemd + curl）；脚本里的 systemctl 在 macOS 不存在 —— 本机只做 bash -n 语法校验
# 验证环境：bash 4+（本机 macOS bash 3.2 仅通过 bash -n 语法校验）
# 验证命令（Linux 上）：
#   ./deploy.sh status
#   ./deploy.sh restart
# 验证状态：语法已通过本机 bash -n 校验；面向 Linux systemd 的实际执行未在本环境验证

set -euo pipefail

APP_NAME="myapp"
APP_USER="myapp"
APP_JAR="/opt/myapp/myapp.jar"
HEALTH_URL="http://127.0.0.1:8080/actuator/health"
LOG_DIR="/var/log/myapp"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*"; }

is_up() {
  # -f 跟随重定向；-s 静默；超时 3s 防挂死；503/500 等也按失败处理（curl 失败即非 0 退出）
  curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1
}

wait_health() {
  local tries="${1:-60}" i=0
  while [ "$i" -lt "$tries" ]; do
    if is_up; then return 0; fi
    i=$((i + 1))
    sleep 1
  done
  return 1
}

cmd_status() {
  if systemctl is-active --quiet "$APP_NAME" && is_up; then
    echo "状态: 运行中且健康（active + health UP）"
    return 0
  elif systemctl is-active --quiet "$APP_NAME"; then
    echo "状态: systemd 认为 active，但健康检查未通过 —— 服务可能正在启动或已不响应"
    return 1
  else
    echo "状态: 未运行"
    return 1
  fi
}

cmd_start() {
  if systemctl is-active --quiet "$APP_NAME"; then
    log "已在运行，跳过 start"
    return 0
  fi
  log "启动 $APP_NAME ..."
  systemctl start "$APP_NAME"
  if wait_health 90; then
    log "启动成功，健康检查通过"
  else
    log "启动失败：健康检查 90s 未通过，请看 journalctl -u $APP_NAME"
    return 1
  fi
}

cmd_stop() {
  # systemctl stop 默认发 SIGTERM（配合 ExecStop/TimeoutStopSec 走优雅停机，见 myapp.service）
  log "停止 $APP_NAME（优雅停机：SIGTERM → 最多等 TimeoutStopSec）..."
  systemctl stop "$APP_NAME"
  log "已停止"
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_logs() {
  journalctl -u "$APP_NAME" -n "${1:-200}" --no-pager
}

cmd_install_unit() {
  # 把仓库里的 myapp.service 装进 systemd（一次性动作，成功后交给 systemctl 管理）
  install -o root -g root -m 0644 myapp.service /etc/systemd/system/myapp.service
  systemctl daemon-reload
  systemctl enable "$APP_NAME"
  log "unit 已安装并开机自启（systemctl enable）"
}

usage() {
  echo "用法: ./deploy.sh {start|stop|restart|status|logs|install-unit} [行数]"
  exit 1
}

case "${1:-}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_restart ;;
  status) cmd_status ;;
  logs) cmd_logs "${2:-}" ;;
  install-unit) cmd_install_unit ;;
  *) usage ;;
esac
