#!/usr/bin/env bash
# scripts/check.sh —— ci-template 的本地质量门禁（与 ci.yml 三条 run 逐条一致）。
#
# 用法：在 ci-template 根执行  ./scripts/check.sh
# 验证状态：已验证（bash 3.2+，cargo 1.92.0；治理后全绿退出 0，演示注入 lint 后红态退出非零）。
# 产物默认落 /tmp/ph21-target 以保教学仓库零残留；真实项目可去掉该行改用本地 target。
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/ph21-target}"

echo "── 1/3 cargo fmt --all --check"
cargo fmt --all --check

echo "── 2/3 cargo clippy --all-targets --workspace -- -D warnings"
cargo clippy --all-targets --workspace -- -D warnings

echo "── 3/3 cargo test --workspace --locked"
cargo test --workspace --locked

echo "✅ 质量门禁全绿"
