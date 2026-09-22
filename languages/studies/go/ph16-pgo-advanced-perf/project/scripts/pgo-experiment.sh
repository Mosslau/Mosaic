#!/usr/bin/env bash
# 来源：ph16-pgo-advanced-perf 综合项目（scripts/pgo-experiment.sh）
# 一句话说明：PGO 实验完整编排——起服务 → 压测期间采 CPU profile → 用 profile
# 构建 PGO 版 → 对比基线 vs PGO 两份延迟/吞吐报告（roadmap §16 推荐项目
# 「API 服务 PGO 实验」的验收动作，配合 README 使用）。
# 依赖：go（本仓库统一 go1.25.6 语言版本档 go 1.25.0）、curl。产物一律 /tmp。
# 用法：
#   ./scripts/pgo-experiment.sh            # 全流程（默认参数见下）
#   OUT=/tmp/mypgo ./scripts/pgo-experiment.sh   # 自定义产物目录
# 验证状态：已验证（go1.25.6 darwin/arm64，2026-09-02；数字随机器波动 ±10~20%）
set -euo pipefail

# ---- 参数（可环境变量覆盖） -------------------------------------------------
OUT="${OUT:-/tmp/ph16proj}"
BASE_ADDR="127.0.0.1:18090"     # 基线版端口
PGO_ADDR="127.0.0.1:18091"      # PGO 版端口（独立端口避免 TIME_WAIT 争用）
DEVICES="${DEVICES:-2048}"
SAMPLES="${SAMPLES:-8192}"
N="${N:-20000}"                 # 正式对比的请求数
WARM_N="${WARM_N:-300000}"      # 采集窗口期间的请求数（要撑满 PROFILE_SECS）
WORKERS="${WORKERS:-8}"         # loadgen 并发
PROFILE_SECS="${PROFILE_SECS:-5}"   # pprof 采集窗口（秒）

mkdir -p "$OUT"

echo "==> [1/5] go test + vet（提交前验收闸之一）"
(cd "$(dirname "$0")/.." && go test ./... && go vet ./...)

echo "==> [2/5] 构建基线版与 loadgen（预编译，避免 go run 首编错过采集窗口）"
BASE_BIN="$OUT/apiserver-base"
LOADGEN_BIN="$OUT/loadgen"
(cd "$(dirname "$0")/.." && go build -o "$BASE_BIN" ./cmd/apiserver && go build -o "$LOADGEN_BIN" ./cmd/loadgen)

echo "==> [3/5] 起基线服务，压测期间采集服务端 CPU profile（${PROFILE_SECS}s 窗口）"
"$BASE_BIN" -addr "$BASE_ADDR" -devices "$DEVICES" -samples "$SAMPLES" &
BASE_PID=""
PGO_PID=""
BASE_PID=$!
trap 'kill $BASE_PID $PGO_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do
  curl -sf "http://$BASE_ADDR/healthz" >/dev/null 2>&1 && break
  sleep 0.1
done
# 大请求数压测把服务持续压到 CPU 忙（WARM_N 需撑满采集窗口：实测 ~50k req/s，
# 5s 窗口 ≈ 25 万请求，故默认 30 万）
"$LOADGEN_BIN" \
    -url "http://$BASE_ADDR" -n "$WARM_N" -workers "$WORKERS" -devices "$DEVICES" \
    >"$OUT/loadgen-warmup.txt" 2>&1 &
LOAD_PID=$!
sleep 1.5   # 等压测进入稳定期
curl -s "http://$BASE_ADDR/debug/pprof/profile?seconds=$PROFILE_SECS" > "$OUT/cpu.pprof"
wait $LOAD_PID || true
echo "  采集 profile: $(wc -c < "$OUT/cpu.pprof") 字节（应明显大于 0；负载打满 CPU 才有代表性）"

echo "==> [4/5] 基线报告（基线服务仍在跑）"
"$LOADGEN_BIN" \
    -url "http://$BASE_ADDR" -n "$N" -workers "$WORKERS" -devices "$DEVICES" \
    > "$OUT/baseline.txt" 2>&1
cat "$OUT/baseline.txt"

echo "==> [5/5] 用 profile 构建 PGO 版，独立端口对比"
PGO_BIN="$OUT/apiserver-pgo"
(cd "$(dirname "$0")/.." && go build -pgo="$OUT/cpu.pprof" -o "$PGO_BIN" ./cmd/apiserver)
"$PGO_BIN" -addr "$PGO_ADDR" -devices "$DEVICES" -samples "$SAMPLES" &
PGO_PID=$!
for _ in $(seq 1 50); do
  curl -sf "http://$PGO_ADDR/healthz" >/dev/null 2>&1 && break
  sleep 0.1
done
"$LOADGEN_BIN" \
    -url "http://$PGO_ADDR" -n "$N" -workers "$WORKERS" -devices "$DEVICES" \
    > "$OUT/pgo.txt" 2>&1
cat "$OUT/pgo.txt"

echo "==> PGO 印章核对（go version -m 应含 -pgo=$OUT/cpu.pprof）"
go version -m "$PGO_BIN" | grep -E '^\s*(build\s+)?-pgo=' || echo '  ⚠️ 未找到 -pgo 印章'

echo
echo "对比两份报告（$OUT/baseline.txt vs $OUT/pgo.txt）："
echo "  关注 p50/p95/p99 与吞吐（req/s）——PGO 收益在接口热点（本工程 90% fnvSigner 去虚拟化）"
echo "  注意：两版跑在不同端口、先后顺序不同，微小差异属正常；看趋势而非绝对值（±10~20%）"
echo "  完整编排说明见 project/README.md 验收标准"
