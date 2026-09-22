#!/usr/bin/env bash
# examples/ex07-script-deploy/health-check.sh —— 独立的探活/诊断脚本（对应主文档 3.1/3.11）
# 教学点：探活要「进程+端口+HTTP 三查」；curl 只看返回码，不看 body 内容会漏掉「200 但 body=DOWN」
# 验证状态：语法已通过本机 bash -n 校验；实际执行需 Linux + 运行中的服务
set -euo pipefail

URL="${1:-http://127.0.0.1:8080/actuator/health}"
TIMEOUT=3

# 1) 进程层（systemd active）
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet myapp; then
    echo "[ok] systemd: myapp active"
  else
    echo "[fail] systemd: myapp 未运行"
    exit 1
  fi
fi

# 2) HTTP 层：body 里真正看 status 字段（避免「200 但实际 DOWN」）
body="$(curl -fsS --max-time "$TIMEOUT" "$URL" 2>/dev/null)" || {
  echo "[fail] 健康检查 HTTP 请求失败: $URL"
  exit 1
}
echo "[ok] health body: $body"
case "$body" in
  *'"status":"UP"'*) echo "[ok] 服务健康 UP" ;;
  *'"status":"DOWN"'*)
    echo "[fail] 服务报告 DOWN（readiness 会摘流量；看日志定位外部依赖）"
    exit 1
    ;;
  *)
    echo "[warn] 响应不是预期格式（可能是非 Actuator 服务）"
    ;;
esac
