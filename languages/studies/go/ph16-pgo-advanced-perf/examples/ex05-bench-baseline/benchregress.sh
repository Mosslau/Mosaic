#!/bin/bash
# 来源：ph16-pgo-advanced-perf 示例 ex05-bench-baseline
# benchregress.sh —— 性能回归基线脚本（benchstat 思路的最小可移植实现）
#
# 思路（与 golang.org/x/perf/cmd/benchstat 同源）：
#   1. 同一基准跑多次（-count=6），用中位数抵抗单次抖动；
#   2. 把结果存成基线文件；
#   3. 之后每次重跑与基线对比，中位数 ns/op 回归超过阈值即失败（exit 1）。
# benchstat 在此基础上还做 Mann-Whitney U 检验给出 p 值；本脚本只做中位数对比，
# 零第三方依赖（只要 bash/awk/sort），足够作为 CI 的第一道回归闸门。
#
# 用法：
#   ./benchregress.sh baseline   # 跑基准并写入基线文件
#   ./benchregress.sh check      # 重跑并与基线对比，回归 > 阈值则 exit 1
#
# 环境变量：
#   THRESHOLD=10        允许的回归百分比（默认 10，随机器波动 ±10~20% 时勿定太小）
#   COUNT=6             采样次数（越多中位数越稳，CI 里权衡时间）
#   BASELINE_FILE=...   基线文件路径（默认 /tmp/ph16/ex05-baseline.txt）
#   CURRENT_FILE=...    本次结果文件（默认 /tmp/ph16/ex05-current.txt）
#
# 验证环境：go1.25.6（darwin/arm64）+ bash 3.2（macOS 自带）+ awk/sort
# 验证状态：已验证（go1.25.6，2026-09-03）
set -euo pipefail

MODE="${1:-}"
THRESHOLD="${THRESHOLD:-10}"
COUNT="${COUNT:-6}"
BASELINE_FILE="${BASELINE_FILE:-/tmp/ph16/ex05-baseline.txt}"
CURRENT_FILE="${CURRENT_FILE:-/tmp/ph16/ex05-current.txt}"

run_bench() {
	# -run='^$' 跳过单测；benchmem 带分配两列；count=N 重复采样
	go test -run='^$' -bench=. -benchmem -count="$COUNT" .
}

# 从 benchmark 输出中提取 "基准名 中位数ns/op"（基准名去掉 -N 后缀）
medians() {
	local file="$1" b
	grep -oE '^Benchmark[A-Za-z0-9_]*' "$file" | sort -u | while read -r b; do
		local med
		med=$(grep "^${b}-" "$file" | awk '{print $3}' | sort -n |
			awk '{a[NR]=$1} END { if (NR==0) exit 1; print (NR%2) ? a[(NR+1)/2] : (a[NR/2]+a[NR/2+1])/2 }')
		echo "$b $med"
	done
}

case "$MODE" in
baseline)
	mkdir -p "$(dirname "$BASELINE_FILE")"
	run_bench | tee "$BASELINE_FILE"
	echo "---"
	echo "基线已写入 ${BASELINE_FILE}（${COUNT} 次采样）："
	medians "$BASELINE_FILE"
	;;
check)
	if [ ! -f "$BASELINE_FILE" ]; then
		echo "基线文件不存在：${BASELINE_FILE}（先跑 ./benchregress.sh baseline）" >&2
		exit 2
	fi
	mkdir -p "$(dirname "$CURRENT_FILE")"
	run_bench | tee "$CURRENT_FILE" >/dev/null
	echo "=== 回归对比（阈值 ${THRESHOLD}%，基线 ${BASELINE_FILE}）==="
	fail=0
	while read -r name base; do
		cur=$(medians "$CURRENT_FILE" | awk -v n="$name" '$1==n {print $2}')
		if [ -z "$cur" ]; then
			echo "MISSING  $name（本次结果中没有该基准）"
			fail=1
			continue
		fi
		delta=$(awk -v b="$base" -v c="$cur" 'BEGIN { printf "%.1f", (c-b)/b*100 }')
		verdict="PASS"
		# awk 做浮点比较：回归超过阈值即失败（负 delta = 变快，永远 PASS）
		if awk -v d="$delta" -v t="$THRESHOLD" 'BEGIN { exit !(d > t) }'; then
			verdict="REGRESSION"
			fail=1
		fi
		printf "%-8s %-28s 基线 %10.1f → 本次 %10.1f ns/op（%+6s%%）\n" \
			"$verdict" "$name" "$base" "$cur" "$delta"
	done < <(medians "$BASELINE_FILE")
	if [ "$fail" -eq 1 ]; then
		echo "存在性能回归（>$THRESHOLD%）" >&2
		exit 1
	fi
	echo "全部基准在阈值内（±$THRESHOLD%）"
	;;
*)
	echo "用法: $0 baseline|check   （THRESHOLD/COUNT/BASELINE_FILE 可用环境变量覆盖）" >&2
	exit 2
	;;
esac
