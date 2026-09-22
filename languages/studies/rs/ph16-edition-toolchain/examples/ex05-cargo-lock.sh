#!/usr/bin/env bash
# examples/ex05-cargo-lock.sh —— Cargo.lock 策略实测：
#   应用（bin）提交锁文件、库（lib）不提交；锁文件格式；升级与回退；--locked 守 CI。
# 验证环境：cargo 1.92.0（macOS arm64）；依赖 itoa 经 rsproxy 镜像拉取
# 运行：bash ex05-cargo-lock.sh（工作目录 /tmp/ph16-ex05-lockdemo，可重复运行）
# 验证状态：已验证（输出为实测，cargo 1.92.0，itoa 1.0.18）
set -eu

WORK=/tmp/ph16-ex05-lockdemo
rm -rf "$WORK" && mkdir -p "$WORK/app/src" "$WORK/mylib/src"
export CARGO_HOME=/tmp/ph16-cargo-home
export CARGO_TARGET_DIR=/tmp/ph16-ex05-target

if [ ! -f "$CARGO_HOME/config.toml" ]; then
    mkdir -p "$CARGO_HOME"
    cat > "$CARGO_HOME/config.toml" <<'TOML'
[source.crates-io]
replace-with = "rsproxy"
[source.rsproxy]
registry = "sparse+https://rsproxy.cn/index/"
TOML
fi

# ---------- 0. 两个 crate：应用与库，git 策略不同 ----------
printf '[package]\nname = "lockdemo-app"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\nitoa = "1"\n' > "$WORK/app/Cargo.toml"
cat > "$WORK/app/src/main.rs" <<'RS'
fn main() {
    let mut buf = itoa::Buffer::new();
    println!("itoa formats 2024 as: {}", buf.format(2024));
}
RS
printf '/target\n' > "$WORK/app/.gitignore"          # 应用：不忽略 Cargo.lock → 提交它

printf '[package]\nname = "lockdemo-lib"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\nitoa = "1"\n' > "$WORK/mylib/Cargo.toml"
echo 'pub fn double(x: u32) -> u32 { x * 2 }' > "$WORK/mylib/src/lib.rs"
printf '/target\nCargo.lock\n' > "$WORK/mylib/.gitignore"  # 库：忽略 Cargo.lock → 不提交

echo "== 1. 应用构建：生成 Cargo.lock（版本 4 格式）=="
( cd "$WORK/app" && cargo build 2>&1 | tail -1 )
echo "--- Cargo.lock 全文（应用要提交的就是它）---"
cat "$WORK/app/Cargo.lock"

echo
echo "== 2. 库也会生成 Cargo.lock，但 .gitignore 忽略它（下游应用说了算）=="
( cd "$WORK/mylib" && cargo build 2>&1 | tail -1 )
echo "mylib/.gitignore:"; cat "$WORK/mylib/.gitignore"
echo "mylib/Cargo.lock 存在与否: $(test -f "$WORK/mylib/Cargo.lock" && echo 存在（本地构建产物，不进 git）)"

echo
echo "== 3. 依赖升级与回退（为依赖升级记录版本并提供回退方案）=="
cd "$WORK/app"
cargo update -p itoa --precise 1.0.14 2>&1 | grep -E 'Downgrading|Updating'
grep -A1 'name = "itoa"' Cargo.lock | head -2
echo "-- 回到最新兼容版 --"
cargo update -p itoa 2>&1 | grep -E 'Updating|Locking'
grep -A1 'name = "itoa"' Cargo.lock | head -2

echo
echo "== 4. --locked：CI 守门员（锁文件过期就拒绝构建）=="
cargo build --locked 2>&1 | tail -1
echo "-- 篡改演示：把 Cargo.toml 的 itoa 改成 \"=1.0.14\"（精确钉死，与锁里的 1.0.18 失配）--"
sed -i '' 's/itoa = "1"/itoa = "=1.0.14"/' Cargo.toml
if cargo build --locked 2>&1 | grep -m1 'the lock file'; then
    echo "--locked 如期拒绝（退出码非 0）"
fi
sed -i '' 's/itoa = "=1.0.14"/itoa = "1"/' Cargo.toml
cargo build --locked 2>&1 | tail -1

# 实测要点（cargo 1.92.0）：
#   - Cargo.lock 头两行注明「自动生成，勿手改」；version = 4（2024 起的锁格式 v4）
#   - cargo update -p itoa --precise 1.0.14 → Downgrading itoa v1.0.18 -> v1.0.14
#   - 锁文件与 Cargo.toml 要求失配时 --locked 报错：
#     "the lock file ... needs to be updated but --locked was passed to prevent this"
