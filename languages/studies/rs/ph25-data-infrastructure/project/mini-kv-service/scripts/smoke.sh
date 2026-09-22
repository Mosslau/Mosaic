#!/usr/bin/env bash
# smoke.sh —— mini-kv-service 的 HTTP 冒烟：CRUD / range scan / 工具权限 / 重启恢复
# 用法：./scripts/smoke.sh    （需 cargo 1.92；二进制自动构建到 $CARGO_TARGET_DIR）
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/ph25-project-target}"
cargo build --release --quiet
BIN="$CARGO_TARGET_DIR/release/mini-kv-service"

DATA="$(mktemp -d /tmp/ph25-mkv-data.XXXXXX)"
PORT="${KV_PORT:-18095}"
cleanup() {
    for pid in "${SRV:-}" "${SRV2:-}"; do
        if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; fi
    done
    rm -rf "$DATA"
}
trap cleanup EXIT

step() { echo; echo "── $1 ──"; }

# —— 第 1 段：写入 + 读取 ——
KV_PORT=$PORT KV_DATA="$DATA" "$BIN" >/tmp/ph25-mkv-s1.log 2>&1 & SRV=$!
sleep 0.8
step "PUT × 3（HTTP CRUD）"
curl -s -X PUT "http://127.0.0.1:$PORT/kv/voltage" -H 'content-type: application/json' -d '{"value":"12.8"}'; echo
curl -s -X PUT "http://127.0.0.1:$PORT/kv/temperature" -H 'content-type: application/json' -d '{"value":"36.5"}'; echo
curl -s -X PUT "http://127.0.0.1:$PORT/kv/pressure" -H 'content-type: application/json' -d '{"value":"1013"}'; echo
step "GET 命中 / DELETE"
curl -s "http://127.0.0.1:$PORT/kv/temperature"; echo
curl -s -o /dev/null -w 'DELETE → %{http_code}\n' -X DELETE "http://127.0.0.1:$PORT/kv/pressure"
step "range scan（start=temperature&end=voltage）"
curl -s "http://127.0.0.1:$PORT/kv?start=temperature&end=voltage"; echo
kill $SRV; wait $SRV 2>/dev/null || true

# —— 第 2 段：重启同一数据目录 → WAL 重放恢复 ——
step "重启恢复（同一 KV_DATA，WAL 重放）"
KV_PORT=$PORT KV_DATA="$DATA" "$BIN" >/tmp/ph25-mkv-s2.log 2>&1 & SRV=$!
sleep 0.8
curl -s "http://127.0.0.1:$PORT/kv/voltage"; echo
curl -s -w ' [%{http_code}]\n' "http://127.0.0.1:$PORT/kv/pressure"   # 已被删除 → 404
step "Agent 工具：writer put → reader 越权写被拒"
curl -s -X POST "http://127.0.0.1:$PORT/tools/call" -H 'content-type: application/json' \
     -H 'x-client-id: writer' -d '{"tool":"kv.put","input":{"key":"odometer","value":"12345"}}'; echo
curl -s -w ' [%{http_code}]\n' -X POST "http://127.0.0.1:$PORT/tools/call" -H 'content-type: application/json' \
     -H 'x-client-id: reader' -d '{"tool":"kv.put","input":{"key":"x","value":"1"}}'
step "metrics / audit"
curl -s "http://127.0.0.1:$PORT/metrics"; echo
curl -s "http://127.0.0.1:$PORT/audit" | head -c 300; echo
step "healthz"
curl -s "http://127.0.0.1:$PORT/healthz"; echo
kill $SRV; wait $SRV 2>/dev/null || true

echo; echo "smoke 全部通过：HTTP CRUD / range scan / 工具权限与审计 / 重启恢复"
