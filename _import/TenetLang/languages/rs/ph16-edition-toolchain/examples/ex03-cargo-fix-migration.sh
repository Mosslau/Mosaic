#!/usr/bin/env bash
# examples/ex03-cargo-fix-migration.sh —— cargo fix --edition 迁移演练：
#   把一个 2015 edition 的 crate 一步步迁到 2024，观察每一步 cargo 自动修了什么、
#   什么必须手工改（Cargo.toml 的 edition 字段、r#try! → ?）。
# 验证环境：cargo 1.92.0（macOS arm64，rustup 管理的 stable）；零第三方依赖，全程离线
# 运行：bash ex03-cargo-fix-migration.sh（工作目录 /tmp/ph16-ex03-migdemo，可重复运行）
# 验证状态：已验证（输出为实测，cargo 1.92.0）
#
# 实测要点（cargo 1.92.0）：
#   1. `cargo fix --edition` 修代码（2015→2018 修 try!→r#try!；2018→2021 修 Box<Fn>→Box<dyn Fn>；
#      2021→2024 修 let gen→let r#gen），并打印 "Migrating Cargo.toml from X edition to Y"——
#      但【实测】它并不改写 Cargo.toml 的 edition 字段，版号必须手工 bump。
#   2. r#try! 只报 deprecated 警告，cargo fix 不会自动改成 `?`，需要手工替换。
#   3. --allow-no-vcs 是因为演练目录不在 git 仓库里；真实项目（在 git 中）不需要该参数，
#      cargo fix 反而要求工作区干净，用 git 状态当「迁移前快照」。
set -eu

WORK=/tmp/ph16-ex03-migdemo
rm -rf "$WORK" && mkdir -p "$WORK/src"
cd "$WORK"
export CARGO_TARGET_DIR=/tmp/ph16-ex03-migdemo-target

# ---------- 0. 一份典型的 2015 年代码 ----------
cat > Cargo.toml <<'TOML'
[package]
name = "migdemo"
version = "0.1.0"
edition = "2015"
TOML

cat > src/main.rs <<'RS'
use std::io;

fn read_port(input: &str) -> Result<u16, io::Error> {
    // try! 宏：? 运算符（1.13）出现之前的错误传播写法
    let n: u16 = try!(input.parse().map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "bad port")));
    Ok(n)
}

// Box<Fn(&str)>：裸 trait object，2018 起警告、2021 起硬错误，应写 Box<dyn Fn(&str)>
fn make_logger() -> Box<Fn(&str)> {
    Box::new(|msg| println!("[log] {}", msg))
}

fn main() {
    let port = read_port("8080").expect("parse");
    let log = make_logger();
    log(&format!("port = {}", port));
    let gen = 1; // gen 在 2024 成为保留关键字
    println!("gen = {}", gen);
}
RS

show_fixes() { # $1=步骤标题
    echo
    echo "===== $1 ====="
    grep -nE 'r#try|Box<dyn|Box<Fn|r#gen|let gen' src/main.rs || true
    grep '^edition' Cargo.toml
}

echo "== 0. 起点：edition 2015，编译只有警告 =="
cargo build 2>&1 | grep -cE '^warning' | xargs echo "警告行数（含明细）:"
show_fixes "起点代码关键行"

echo
echo "== 1. cargo fix --edition（2015 → 2018 兼容修复）=="
cargo fix --edition --allow-no-vcs 2>&1 | grep -E 'Migrating|Fixed|Finished'
show_fixes "fix 之后：try! 被改成 r#try!（2018 里 try 是保留关键字，先转义保编译）"

echo "-- 手工步骤 A：bump Cargo.toml 到 2018（cargo fix 不改它，实测）--"
sed -i '' 's/edition = "2015"/edition = "2018"/' Cargo.toml
cargo fix --edition-idioms --allow-no-vcs 2>&1 | grep -E 'Fixed|Finished|warning' | head -3
cargo build 2>&1 | grep -m1 -E 'deprecated|r#try' || true

echo
echo "== 2. cargo fix --edition（2018 → 2021）=="
cargo fix --edition --allow-no-vcs 2>&1 | grep -E 'Migrating|Fixed|Finished'
show_fixes "fix 之后：Box<Fn> 被改成 Box<dyn Fn>"

echo "-- 手工步骤 B：bump 到 2021，并把 r#try! 手工换成 ?（cargo fix 不做这一步，实测）--"
sed -i '' 's/edition = "2018"/edition = "2021"/' Cargo.toml
python3 - <<'PY'
p = 'src/main.rs'
s = open(p).read()
s = s.replace(
    'let n: u16 = r#try!(input.parse().map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "bad port")));',
    'let n: u16 = input.parse().map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "bad port"))?;')
open(p, 'w').write(s)
PY
cargo fix --edition-idioms --allow-no-vcs 2>&1 | grep -E 'Fixed|Finished' | head -2
cargo build 2>&1 | tail -1

echo
echo "== 3. cargo fix --edition（2021 → 2024）=="
cargo fix --edition --allow-no-vcs 2>&1 | grep -E 'Migrating|Fixed|Finished'
show_fixes "fix 之后：let gen 被改成 let r#gen（2024 保留关键字，先转义保编译）"

echo "-- 手工步骤 C：bump 到 2024 --"
sed -i '' 's/edition = "2021"/edition = "2024"/' Cargo.toml
cargo fix --edition-idioms --allow-no-vcs 2>&1 | grep -E 'Fixed|Finished' | head -2

echo
echo "== 4. 终验：2024 edition 零警告构建 + 运行 =="
RUSTFLAGS="-D warnings" cargo build 2>&1 | tail -1
"$CARGO_TARGET_DIR/debug/migdemo"
grep '^edition' Cargo.toml
