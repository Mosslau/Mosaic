#!/usr/bin/env bash
# verify-local.sh —— 练习 1 参考解：在本地按 CI 的 step 顺序复刻门禁，验证 ci.yml 内容可行。
# 验证状态：已验证（cargo 1.92.0 本机实测退出 0）。产物落 /tmp 保仓库零残留。
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/ph21-target}"

echo "── 1/3 cargo fmt --all --check"
cargo fmt --all --check

echo "── 2/3 cargo clippy --all-targets --workspace -- -D warnings"
cargo clippy --all-targets --workspace -- -D warnings

echo "── 3/3 cargo test --workspace"
cargo test --workspace

echo "✅ 本地复刻的 CI 门禁全绿"
