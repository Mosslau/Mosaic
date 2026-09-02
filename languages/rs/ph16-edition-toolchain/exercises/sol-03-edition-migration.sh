#!/usr/bin/env bash
# 来源：languages/rs/ph16-edition-toolchain/exercises/README.md 练习 3
# 说明：Edition 迁移演练参考实现 —— 2015 → 2018 → 2021 → 2024，逐步记录谁改了什么。
#       起点代码与 examples/ex03 不同（async 变量名 + 裸 extern 块 + 引用形态裸 trait object）。
# 验证环境：cargo 1.92.0（macOS arm64）；零第三方依赖，全程离线
# 运行：bash sol-03-edition-migration.sh（工作目录 /tmp/ph16-sol03，可重复运行）
# 验证状态：已验证（cargo 1.92.0；终验零警告，运行输出 "pending 7 abs(-3) = 3"）
#
# 迁移记录（实测）：
#   步骤 1（2015→2018）cargo fix --edition：Fixed src/main.rs (3 fixes)
#     自动修：try! → r#try!；let async → let r#async（2018 起 async/try 是保留关键字，先转义保编译）
#     手工：bump Cargo.toml edition = "2018"（cargo fix 打印 Migrating Cargo.toml 但不改写它）
#   步骤 2（2018→2021）cargo fix --edition：Fixed src/main.rs (1 fix)
#     自动修：&Fn(i32) -> i32 → &dyn Fn(i32) -> i32（裸 trait object 在 2021 是硬错误）
#     手工：bump edition = "2021"；r#try! → ?（deprecated 警告，cargo fix 不动它）
#   步骤 3（2021→2024）cargo fix --edition：Fixed src/main.rs (1 fix)
#     自动修：extern "C" { ... } → unsafe extern "C" { ... }（2024 强制）
#     手工：bump edition = "2024"
#   终验：RUSTFLAGS="-D warnings" cargo build 零警告；运行输出 pending 7 abs(-3) = 3
set -eu

WORK=/tmp/ph16-sol03
rm -rf "$WORK" && mkdir -p "$WORK/src"
cd "$WORK"
export CARGO_TARGET_DIR=/tmp/ph16-sol03-target

printf '[package]\nname = "sol03"\nversion = "0.1.0"\nedition = "2015"\n' > Cargo.toml
cat > src/main.rs <<'RS'
use std::io;

extern "C" { fn abs(input: i32) -> i32; }

fn parse_nonneg(input: &str) -> Result<u32, io::Error> {
    let n = try!(input.parse::<u32>().map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "bad number")));
    Ok(n)
}

fn describe(f: &Fn(i32) -> i32) -> String {
    format!("abs(-3) = {}", f(-3))
}

fn main() {
    let async = "pending";
    let n = parse_nonneg("7").expect("parse");
    println!("{} {} {}", async, n, describe(&|x| unsafe { abs(x) }));
}
RS

bump() { sed -i '' "s/edition = \"$1\"/edition = \"$2\"/" Cargo.toml; grep '^edition' Cargo.toml; }

echo "===== 步骤 1：2015 → 2018 ====="
cargo fix --edition --allow-no-vcs 2>&1 | grep -E 'Migrating|Fixed'
grep -nE 'r#try|r#async' src/main.rs
bump 2015 2018

echo "===== 步骤 2：2018 → 2021 ====="
cargo fix --edition --allow-no-vcs 2>&1 | grep -E 'Migrating|Fixed'
grep -n 'dyn Fn' src/main.rs
bump 2018 2021
# 手工：r#try! → ?（cargo fix 只做转义保编译，不做语义现代化）
python3 - <<'PY'
p = 'src/main.rs'
s = open(p).read()
s = s.replace(
    'let n = r#try!(input.parse::<u32>().map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "bad number")));',
    'let n = input.parse::<u32>().map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "bad number"))?;')
open(p, 'w').write(s)
PY
cargo build 2>&1 | tail -1

echo "===== 步骤 3：2021 → 2024 ====="
cargo fix --edition --allow-no-vcs 2>&1 | grep -E 'Migrating|Fixed'
grep -n 'unsafe extern' src/main.rs
bump 2021 2024

echo "===== 终验 ====="
RUSTFLAGS="-D warnings" cargo build 2>&1 | tail -1
"$CARGO_TARGET_DIR/debug/sol03"
