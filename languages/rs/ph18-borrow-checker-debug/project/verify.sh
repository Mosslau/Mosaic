#!/usr/bin/env bash
# verify.sh —— 借用错误练习集自动验证器
#
# 遍历 cases/*/，对每个案例做三件事：
#   1) error.rs 必须编译失败，且诊断输出里出现 error.rs 头部声明的期望错误码
#      （机器可读标记行格式：// expect-error: E0XXX，写在本文件头部注释里）
#   2) fix.rs 必须编译通过
#   3) 全部通过才返回 0；任一失败返回 1，便于挂进 CI（完整 CI 体系见 ph21）
#
# 用法：bash verify.sh
# 验证环境：rustc 1.92.0（macOS arm64，已验证：本脚本在 project/cases 三案例上实测通过）；
#           产物一律输出到系统临时目录，不污染本仓库。
set -u

here="$(cd "$(dirname "$0")" && pwd)"
cases_dir="$here/cases"
out_dir="${TMPDIR:-/tmp}/ph18-borrow-checker-verify"
mkdir -p "$out_dir"
edition="2021"

pass=0
fail=0

for case_dir in "$cases_dir"/*/; do
    [ -f "$case_dir/error.rs" ] || continue
    name="$(basename "$case_dir")"

    expected="$(grep -oE 'expect-error: E[0-9]+' "$case_dir/error.rs" | head -1 | awk '{print $2}')"
    if [ -z "$expected" ]; then
        echo "[SKIP] $name —— error.rs 缺少 // expect-error: E0XXX 标记行"
        fail=$((fail + 1))
        continue
    fi

    # 1) error.rs 必须编译失败且带期望错误码
    err_out="$(rustc --edition "$edition" -o "$out_dir/${name}-err" "$case_dir/error.rs" 2>&1)"
    rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "[FAIL] $name —— error.rs 竟然编译通过了，期望编译失败 ($expected)"
        fail=$((fail + 1))
    elif printf '%s' "$err_out" | grep -q "error\[$expected\]"; then
        echo "[PASS] $name —— error.rs 如期报 $expected"
        pass=$((pass + 1))
    else
        echo "[FAIL] $name —— error.rs 编译失败，但错误码不是 $expected："
        printf '%s\n' "$err_out" | grep -E '^error' | head -3 | sed 's/^/       /'
        fail=$((fail + 1))
    fi

    # 2) fix.rs 必须编译通过
    fix_out="$(rustc --edition "$edition" -o "$out_dir/${name}-fix" "$case_dir/fix.rs" 2>&1)"
    rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "[PASS] $name —— fix.rs 编译通过"
        pass=$((pass + 1))
    else
        echo "[FAIL] $name —— fix.rs 编译失败："
        printf '%s\n' "$fix_out" | grep -E '^error' | head -3 | sed 's/^/       /'
        fail=$((fail + 1))
    fi
done

echo "----"
echo "结果：通过 $pass 项，失败 $fail 项"
[ "$fail" -eq 0 ]
