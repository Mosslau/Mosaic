#!/usr/bin/env bash
# scripts/check.sh —— sol-03 参考解：单 crate（非 workspace）形态的本地质量门禁。
#
# 用法：在 cfg-app 根执行  ./scripts/check.sh
# 验证状态：已验证（bash 3.2+，cargo 1.92.0；干净退出 0，注入 lint 后第二步失败退出非零）。
# 与 ex06 的 workspace 版对比可见两种命令形态：
#   单 crate：cargo fmt --check / cargo clippy --all-targets -- -D warnings / cargo test
#   workspace：各加 --all / --workspace（ex06）
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/ph21-target}"

echo "── 1/3 cargo fmt --check"
cargo fmt --check

echo "── 2/3 cargo clippy --all-targets -- -D warnings"
cargo clippy --all-targets -- -D warnings

echo "── 3/3 cargo test"
cargo test

echo "✅ 质量门禁全绿"
