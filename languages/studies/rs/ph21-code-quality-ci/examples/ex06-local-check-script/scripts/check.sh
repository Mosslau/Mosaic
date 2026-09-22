#!/usr/bin/env bash
# scripts/check.sh —— ex06 本地质量门禁（workspace 根执行）。
#
# 用法：
#   ./scripts/check.sh            本地自检：fmt → clippy → test 全过才退出 0
#
# 设计要点（主文档 3.7）：
#   - set -euo pipefail：任何一步非零立即退出；未定义变量报错；管道失败算失败
#   - 门禁顺序 = 最便宜的在前：fmt(毫秒级) → clippy → test(最贵最后)
#   - workspace 命令形态：fmt --all / clippy --workspace / test --workspace
# 验证状态：已验证（bash 3.2+，cargo 1.92.0；干净退出 0，注入 lint 后在第 2 步失败）。
set -euo pipefail

# 无论从哪个目录调用，都先切到脚本所在 workspace 根
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="$HOME/.cargo/bin:$PATH"
# 构建产物默认落 /tmp（本教学仓库要求零二进制残留）；真实项目去掉下面这行即用本地 target。
# 已显式设置 CARGO_TARGET_DIR 时尊重调用方。
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/ph21-target}"

echo "── 1/3 cargo fmt --all --check"
cargo fmt --all --check

echo "── 2/3 cargo clippy --all-targets --workspace -- -D warnings"
cargo clippy --all-targets --workspace -- -D warnings

echo "── 3/3 cargo test --workspace"
cargo test --workspace

echo "✅ 质量门禁全绿"
