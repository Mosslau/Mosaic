#!/usr/bin/env bash
# examples/ex04-msrv-check.sh —— MSRV 实战：声明、解析器行为、依赖 MSRV 检查
# 演示三件事（全部本环境实测）：
#   1. resolver v3（edition 2024 默认）的 MSRV 感知：rust-version = "1.85" 的项目，
#      依赖 home 的最新版 0.5.12 要求 Rust 1.88，cargo 自动降到兼容的 0.5.11；
#      对照组 edition 2021（resolver v2）直接选最新 0.5.12，不管 MSRV。
#   2. 用 cargo metadata 提取依赖树里每个包的 rust_version（依赖的 MSRV 声明）。
#   3. 若装了 cargo-msrv（本环境已装 0.19.3），再演示 cargo msrv show / list。
# 验证环境：cargo 1.92.0（macOS arm64）；依赖经 rsproxy 镜像拉取；python3 解析 JSON
# 运行：bash ex04-msrv-check.sh（工作目录 /tmp/ph16-ex04-msrv，可重复运行）
# 验证状态：已验证（resolver 矩阵与 metadata 提取实测；cargo msrv verify 因沙箱禁写
#           ~/.rustup 无法安装旧工具链，未在本环境验证——真实环境可直接跑）
set -u

WORK=/tmp/ph16-ex04-msrv
rm -rf "$WORK" && mkdir -p "$WORK"
export CARGO_HOME=/tmp/ph16-cargo-home
export CARGO_TARGET_DIR=/tmp/ph16-ex04-target

# 国内镜像（已存在则跳过；海外网络可删掉 config.toml 用默认 crates.io）
if [ ! -f "$CARGO_HOME/config.toml" ]; then
    mkdir -p "$CARGO_HOME"
    cat > "$CARGO_HOME/config.toml" <<'TOML'
[source.crates-io]
replace-with = "rsproxy"
[source.rsproxy]
registry = "sparse+https://rsproxy.cn/index/"
TOML
fi

mkproj() { # $1=目录 $2=edition $3=可选 rust-version 行
    mkdir -p "$1/src"
    printf '[package]\nname = "%s"\nversion = "0.1.0"\nedition = "%s"\n%s\n\n[dependencies]\nhome = "0.5"\n' \
        "$(basename "$1")" "$2" "$3" > "$1/Cargo.toml"
    echo 'fn main() { println!("home = {:?}", home::home_dir()); }' > "$1/src/main.rs"
}

# ---------- 1. resolver v3 vs v2：同一依赖，两种结局 ----------
mkproj "$WORK/msrv-aware"   2024 'rust-version = "1.85"'
mkproj "$WORK/semver-only"  2021 ''

echo "== 1a. edition 2024 + rust-version 1.85（resolver v3，MSRV 感知）=="
( cd "$WORK/msrv-aware" && cargo generate-lockfile 2>&1 | grep -E 'Adding|Locking' )
grep -A1 'name = "home"' "$WORK/msrv-aware/Cargo.lock"

echo
echo "== 1b. edition 2021 无 rust-version（resolver v2，只看 semver 最新）=="
( cd "$WORK/semver-only" && cargo generate-lockfile 2>&1 | grep -E 'Adding|Locking' )
grep -A1 'name = "home"' "$WORK/semver-only/Cargo.lock"

# ---------- 2. cargo metadata 提取依赖的 rust_version ----------
echo
echo "== 2. 依赖树里每个包的 MSRV 声明（cargo metadata + python3）=="
( cd "$WORK/msrv-aware" && cargo metadata --format-version 1 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [(p["name"], p["version"], p.get("rust_version") or "（未声明）") for p in d["packages"]]
for name, ver, rv in sorted(rows, key=lambda r: (r[2], r[0])):
    print(f"  {name} {ver}: rust-version = {rv}")
' )

# ---------- 3. cargo-msrv（若已安装）----------
echo
if command -v cargo-msrv >/dev/null 2>&1 || [ -x "$CARGO_HOME/bin/cargo-msrv" ]; then
    export PATH="$CARGO_HOME/bin:$PATH"
    # cargo-msrv 要在 $HOME 下建日志目录；沙箱/受限环境里把 HOME 指到可写目录，
    # 同时显式保留 RUSTUP_HOME 让 rustup 代理仍能找到工具链（本环境实测需要）
    ORIG_HOME="$HOME"
    export HOME=/tmp/ph16-ex04-home RUSTUP_HOME="${RUSTUP_HOME:-$ORIG_HOME/.rustup}"
    mkdir -p "$HOME"
    echo "== 3. cargo msrv show / list（cargo-msrv $(cargo msrv --version | awk '{print $2}')）=="
    ( cd "$WORK/msrv-aware" && cargo msrv show 2>&1 | grep -v '^\[' ; cargo msrv list 2>&1 | sed 's/\x1b\[[0-9;]*m//g' )
    export HOME="$ORIG_HOME"
else
    echo "== 3. cargo-msrv 未安装，跳过（安装：cargo install cargo-msrv --locked）=="
fi

echo
echo "注意：cargo msrv verify（逐版本装旧工具链实测最低可编译版本）需要 rustup 联网安装工具链；"
echo "本环境沙箱禁写 ~/.rustup，未验证。真实环境：cd 项目 && cargo msrv verify"

# 实测输出（cargo 1.92.0 / cargo-msrv 0.19.3，rsproxy 镜像）：
#   1a. Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)  → lock 选中 0.5.11
#   1b. Locking 3 packages ...                                       → lock 选中 0.5.12
#   2. home 0.5.11: rust-version = 1.81；windows-sys 0.61.2: rust-version = 1.71（等）
#   3. cargo msrv show → MSRV is Rust 1.85.0；list 表格列出各依赖 MSRV
