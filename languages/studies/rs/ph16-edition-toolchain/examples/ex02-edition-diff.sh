#!/usr/bin/env bash
# examples/ex02-edition-diff.sh —— Edition 差异实测矩阵：
#   同一份代码分别用 --edition 2015/2018/2021/2024 编译，亲眼看「同一编译器按 edition 切换语义」。
# 覆盖的差异点（全部本环境实测）：
#   A. disjoint closure capture：move 闭包在 2015/2018 整体捕获，2021+ 只捕获用到的字段
#   B. array.into_iter()：2015/2018 按引用迭代（历史怪癖），2021+ 按值迭代
#   C. gen 关键字：2024 起 gen 成为保留关键字
#   D. extern 块：2024 起必须写 unsafe extern
# 验证环境：rustc 1.92.0（macOS arm64，rustup 管理的 stable，一条 rustc 支持全部四个 edition）
# 运行：bash ex02-edition-diff.sh
# 验证状态：已验证（矩阵输出为实测，rustc 1.92.0）
set -u

WORK=/tmp/ph16-ex02-edition-diff
rm -rf "$WORK" && mkdir -p "$WORK"
cd "$WORK"

# ---------- A. disjoint closure capture（2018 → 2021 变化） ----------
cat > a_closure_capture.rs <<'RS'
struct Config {
    host: String,
    port: u16,
}

fn main() {
    let cfg = Config { host: "localhost".to_string(), port: 8080 };
    // move 闭包：2015/2018 整体捕获 cfg（连同没用到的 port）；2021+ 只捕获真正用到的 cfg.host
    let show_host = move || println!("host = {}", cfg.host);
    show_host();
    println!("port = {}", cfg.port);
}
RS

# ---------- B. array into_iter（2018 → 2021 变化） ----------
cat > b_array_into_iter.rs <<'RS'
fn main() {
    let arr = [10, 20, 30];
    for x in arr.into_iter() {
        let _: i32 = x; // 2015/2018：x 是 &i32（类型错）；2021+：x 是 i32
        println!("{x}");
    }
}
RS

# ---------- C. gen 关键字（2021 → 2024 变化） ----------
cat > c_gen_keyword.rs <<'RS'
fn main() {
    let gen = 42; // 2024 起 gen 是保留关键字（为将来的 gen block 生成器语法预留）
    println!("{gen}");
}
RS

# ---------- D. extern 块必须 unsafe（2021 → 2024 变化） ----------
cat > d_unsafe_extern.rs <<'RS'
extern "C" { fn abs(input: i32) -> i32; }
fn main() {
    println!("{}", unsafe { abs(-3) });
}
RS

echo "== Edition 编译矩阵（rustc $(rustc --version | awk '{print $2}')，-D warnings）=="
printf '%-22s' "案例 \ edition"
for ed in 2015 2018 2021 2024; do printf '%-14s' "$ed"; done
echo

try_compile() { # $1=file $2=edition -> 0 ok / 1 fail（错误文本按 文件.edition 存档）
    local base="${1%.rs}"
    rustc --edition "$2" -D warnings "$1" -o "$WORK/out.$base.$2" 2>"$WORK/err.$base.$2"
}

for f in a_closure_capture b_array_into_iter c_gen_keyword d_unsafe_extern; do
    printf '%-22s' "$f"
    for ed in 2015 2018 2021 2024; do
        if try_compile "$f.rs" "$ed"; then
            printf '%-14s' "通过"
        else
            printf '%-14s' "失败"
        fi
    done
    echo
done

echo
echo "== 失败案例的首条错误（实测原文摘录）=="
for key in a_closure_capture:2018 b_array_into_iter:2018 c_gen_keyword:2024 d_unsafe_extern:2024; do
    f="${key%%:*}"; ed="${key##*:}"
    echo "--- $f.rs @ edition $ed ---"
    grep -m1 -A2 -E '^error' "$WORK/err.$f.$ed" | head -5
done

echo
echo "== 2021 编译通过版本的运行输出 =="
rustc --edition 2021 -D warnings a_closure_capture.rs -o "$WORK/a21" && "$WORK/a21"
rustc --edition 2021 -D warnings b_array_into_iter.rs -o "$WORK/b21" && "$WORK/b21"
rustc --edition 2021 -D warnings c_gen_keyword.rs   -o "$WORK/c21" && "$WORK/c21"
rustc --edition 2021 -D warnings d_unsafe_extern.rs -o "$WORK/d21" && "$WORK/d21"

# 实测矩阵（rustc 1.92.0）：
#   a_closure_capture   2015 失败(E0382) / 2018 失败(E0382) / 2021 通过 / 2024 通过
#   b_array_into_iter   2015 失败(E0308) / 2018 失败(E0308) / 2021 通过 / 2024 通过
#   c_gen_keyword       2015 通过 / 2018 通过 / 2021 通过 / 2024 失败(gen 是保留关键字)
#   d_unsafe_extern     2015 通过 / 2018 通过 / 2021 通过 / 2024 失败(extern blocks must be unsafe)
