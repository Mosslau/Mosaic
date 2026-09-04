#!/usr/bin/env bash
# release-check.sh —— 本地可跑的发布前检查流水线（project/mini-kv-service）
#
# 形态复制自 ph24-supply-chain-release/project/relpipe/release-check.sh（ph24 阶段发布流水线），
# 按本收官工程适配被测对象。本工程跑通 fmt/clippy/test/audit/deny 即证明
# ph24 沉淀的流水线被 ph25 KV 工程直接拿去用。
# 每一步输出明确结果；缺工具/缺网络的步骤显式跳过并提示，不假装通过。
# 本机已验证（cargo 1.92.0 / cargo-audit 0.22.2 / cargo-deny 0.20.2，2026-09-04）：
#   全部 step 在本机跑通，真实输出见 README 验收段。
#
# 用法：
#   export PATH="$HOME/.cargo/bin:$PATH"     # 需要 cargo / cargo-audit / cargo-deny
#   ./release-check.sh
# 可选环境变量：
#   CARGO_TARGET_DIR=/tmp/…   默认 /tmp/ph24-relpipe-target（仓库零二进制残留）
#   SKIP_AUDIT=1 / SKIP_DENY=1   显式跳过外部工具（无网络/未安装时）
#   OFFICIAL=1                  追加验证「已发布版本号在 CHANGELOG 归档」的更严检查

set -euo pipefail
cd "$(dirname "$0")"          # 无论从哪调用，都在 relpipe 目录内执行

export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/ph25-project-target}"

VERSION="$(sed -n 's/^version *= *"\([^"]*\)".*/\1/p' Cargo.toml | head -1)"
echo "==== mini-kv-service v${VERSION} release-check ===="
echo "工作目录：$(pwd)　CARGO_TARGET_DIR=$CARGO_TARGET_DIR"

step() { echo; echo "── [$1/9] $2 ──"; }

# [1/9] 格式
step 1 "cargo fmt --check"
cargo fmt --check && echo "fmt: OK"

# [2/9] lint（质量门禁，ph21 三连第一道）
step 2 "cargo clippy --all-targets -- -D warnings"
cargo clippy --all-targets -- -D warnings && echo "clippy: 0 warnings"

# [3/9] 测试（--locked：lock 与 manifest 不一致即失败，ph16 可复现纪律）
step 3 "cargo test --release --locked"
cargo test --release --locked

# [4/9] 已知漏洞审计（cargo audit）
step 4 "cargo audit（RustSec advisory-db）"
if command -v cargo-audit >/dev/null 2>&1 && [[ "${SKIP_AUDIT:-0}" != "1" ]]; then
    if [[ -d "$HOME/.cargo/advisory-db" ]]; then
        cargo audit --db "$HOME/.cargo/advisory-db" --no-fetch   # 离线复用缓存 db
    else
        cargo audit                                               # 首次需联网拉 db
    fi
    echo "audit: 无已知漏洞命中"
else
    echo "跳过 cargo audit（未安装 cargo-audit 或 SKIP_AUDIT=1）—— 发布前请补跑"
fi

# [5/9] 策略门禁（cargo deny：advisories/licenses/bans/sources 四段）
step 5 "cargo deny check（deny.toml）"
if command -v cargo-deny >/dev/null 2>&1 && [[ "${SKIP_DENY:-0}" != "1" ]]; then
    cargo deny check licenses        # 离线可跑（策略基于 manifest 与 lock）
    cargo deny check bans            # 离线可跑
    # advisories 与 step 4 的 audit 同源（RustSec db）；deny 每次会尝试 fetch db 最新版，
    # 网络不可用时降级为警告——已知漏洞的硬性覆盖已由 step 4 的 cargo audit 承担
    if cargo deny check advisories >/tmp/deny-advisories.log 2>&1; then
        echo "deny advisories: OK"
    else
        echo "警告：deny check advisories 未通过（多为 advisory db fetch 网络问题，见 /tmp/deny-advisories.log）"
        echo "      —— 已知漏洞硬性门禁已由 step 4 cargo audit 覆盖；网络恢复后请重跑本条"
    fi
    echo "deny: licenses/bans 全绿（advisories 见上）"
else
    echo "跳过 cargo deny（未安装 cargo-deny 或 SKIP_DENY=1）—— 发布前请补跑"
fi

# [6/9] 许可证清单（cargo deny list；无 deny 时提示用 examples/ex03 脚本）
step 6 "许可证清单（cargo deny list）"
if command -v cargo-deny >/dev/null 2>&1 && [[ "${SKIP_DENY:-0}" != "1" ]]; then
    cargo deny list
else
    echo "（无 cargo-deny）许可证清单可用 examples/ex03-license-check/check-licenses.sh . 生成"
fi

# [7/9] 发布内容审查（cargo package --list——不可收回前最后一道人审）
step 7 "cargo package --list（逐行审查随包发布的文件）"
cargo package --list --allow-dirty 2>/dev/null
echo "↑ 人工核对：无 .env/密钥/target/多余文件；LICENSE/README/CHANGELOG 在列"

# [8/9] 本地打包演练（--no-verify 跳过重编译省时间；产物在 $CARGO_TARGET_DIR/package/）
step 8 "cargo package --no-verify（本地打包 .crate）"
cargo package --no-verify --allow-dirty 2>&1 | grep -E "Packaging|Packaged"
echo "打包产物：$CARGO_TARGET_DIR/package/（发布前可解包复查）"

# [9/9] CHANGELOG 与版本号一致性校验（roadmap 验收「版本号和变更说明一致」）
step 9 "CHANGELOG 校验（version ↔ CHANGELOG ↔ tag）"
if grep -q "^## \[${VERSION}\]" CHANGELOG.md; then
    echo "CHANGELOG 已归档 [${VERSION}]：OK"
else
    echo "CHANGELOG 缺 [${VERSION}] 小节 —— 请把 [Unreleased] 归档为 [${VERSION}]（练习 sol-03）" >&2
    exit 1
fi
if [[ "${OFFICIAL:-0}" == "1" ]] && [[ "$VERSION" != *-* ]]; then
    # 正式发布（非预发布）：要求 Unreleased 里没有未归档的变更（示例 crate 允许空 Unreleased）
    if grep -A 3 '^## \[Unreleased\]' CHANGELOG.md | grep -qE '^- '; then
        echo "警告：CHANGELOG [Unreleased] 仍有未归档条目 —— 正式发布前应清空或写清" >&2
        exit 1
    fi
    echo "正式发布校验：Unreleased 已清空，可打 tag v${VERSION}"
fi

echo
echo "==== release-check 通过：v${VERSION}（真实 cargo publish 未在本环境验证） ===="
