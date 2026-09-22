// 来源：languages/rs/ph15-macros-metaprogramming/exercises/README.md 练习 3
// 说明：递归声明宏（tt muncher 模式）——每层调用从参数列表「剥掉一个」再递归处理剩余，
//       直到只剩一个参数（递归终点）。这是 macro_rules! 里最常用的递归骨架。
//       附带两个「宏不做算术」的陷阱：① 求和只能逐个枚举参数调用——写
//       sum_args!(1..=10) 会被单参终点臂原样返回整个 range（见下方 sum_args!
//       定义前的注释与实测 Debug 输出）；② 对数值做递归（如从 3 减到 0）永远
//       不会命中字面量终点（宏按 token 匹配、不先求值），会递归到展开深度上限
//       报错（实测文本见下）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-03-recursion-macros.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告；下方输出为实测）
//
// 实测输出：
//   1. sum_args!(1, 2, 3, 4) = 10
//   2. sum_args!(1, 2, 3, 4, 5, 6, 7, 8, 9, 10) = 55
//   3. last_arg!("a", "b", "c") = c
//   4. 单参数是递归终点：sum_args!(42) = 42, last_arg!("only") = only
//   断言全部通过
//   陷阱实测：把 down_from!(3) 的注释去掉再编译，会报
//     error: recursion limit reached while expanding `down_from!`
//   （见文件底部注释，勿在本文件启用——启用即编译失败）

// 递归求和：剥掉第一个参数，递归处理剩余
// 注意：只能逐个枚举参数调用，如 sum_args!(1, 2, 3, 4)；
//       sum_args!(1..=10) 会把 1..=10 当单个参数、命中终点臂原样返回整个 range——
//       宏按 token 匹配不做算术，不会替你遍历 range（实测 Debug 输出就是 1..=10）。
macro_rules! sum_args {
    ($x:expr) => {
        $x // 递归终点：只剩一个参数，直接返回
    };
    ($first:expr, $($rest:expr),+) => {
        $first + sum_args!($($rest),+) // 剥一个 + 递归剩余
    };
}

// 递归取最后一个参数
macro_rules! last_arg {
    ($x:expr) => {
        $x // 递归终点
    };
    ($first:expr, $($rest:expr),+) => {
        last_arg!($($rest),+) // 丢掉第一个，继续递归
    };
}

// 陷阱（默认注释掉——启用即编译失败，勿在验收时打开）：
// macro_rules! down_from {
//     (0) => {};
//     ($n:expr) => { down_from!($n - 1) };
// }
// down_from!(3) 展开为 down_from!(3 - 1) -> down_from!((3 - 1) - 1) -> ...
// $n - 1 是一串 token，宏匹配不会先做算术把它算成字面量 0，
// 所以永远到不了 (0) 臂，一路展开到深度上限：
//   error: recursion limit reached while expanding `down_from!`
// 教训：macro_rules! 递归靠「结构（token 列表）变短」收敛，不靠「值变小」。

fn main() {
    // 1. 递归求和
    println!("1. sum_args!(1, 2, 3, 4) = {}", sum_args!(1, 2, 3, 4));
    println!(
        "2. sum_args!(1, 2, 3, 4, 5, 6, 7, 8, 9, 10) = {}",
        sum_args!(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    );
    assert_eq!(sum_args!(1, 2, 3, 4), 10);
    assert_eq!(sum_args!(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 55);

    // 2. 递归取最后一个
    println!(
        "3. last_arg!(\"a\", \"b\", \"c\") = {}",
        last_arg!("a", "b", "c")
    );
    assert_eq!(last_arg!("a", "b", "c"), "c");

    // 3. 单参数直接命中递归终点
    println!(
        "4. 单参数是递归终点：sum_args!(42) = {}, last_arg!(\"only\") = {}",
        sum_args!(42),
        last_arg!("only")
    );
    assert_eq!(sum_args!(42), 42);
    assert_eq!(last_arg!("only"), "only");
    println!("断言全部通过");
}
