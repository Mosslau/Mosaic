// 来源：languages/rs/ph15-macros-metaprogramming/exercises/README.md 练习 2
// 说明：swap_vars! 宏——用显式临时变量交换两个「调用方变量」（ident 传入）。
//       卫生性实战：宏体内声明的临时变量 tmp 不与调用方同名变量冲突；
//       而传入的 ident（left/right）指向调用方作用域，宏因此能改写它们。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-02-swap-hygiene.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告；下方输出为实测）
//
// 实测输出：
//   1. 调用方也有一个 tmp = 99，宏体内还要用 tmp 当临时变量
//   2. swap_vars!(left, right) 后: left = 2, right = 1
//   3. 调用方 tmp 仍是 99 —— 宏内临时变量未泄漏/未冲突（卫生性实测）
//   4. swap_vars!(left, right) 再交换回来: left = 1, right = 2
//   断言全部通过

macro_rules! swap_vars {
    ($a:ident, $b:ident) => {{
        let tmp = $a; // 宏体内造的 tmp 是卫生的：标记为宏定义处上下文
        $a = $b; // $a / $b 是调用方传进来的 ident：解析到调用方作用域
        $b = tmp;
    }};
}

fn main() {
    let mut left = 1;
    let mut right = 2;

    // 调用方恰好也声明了一个 tmp——若宏体内的 tmp 不卫生，这里就会冲突
    let tmp = 99;
    println!("1. 调用方也有一个 tmp = {tmp}，宏体内还要用 tmp 当临时变量");

    swap_vars!(left, right);
    println!("2. swap_vars!(left, right) 后: left = {left}, right = {right}");
    println!("3. 调用方 tmp 仍是 {tmp} —— 宏内临时变量未泄漏/未冲突（卫生性实测）");
    assert_eq!((left, right), (2, 1));
    assert_eq!(tmp, 99);

    // 再交换回来：证明 swap 对任意 ident 组合可重复调用
    swap_vars!(left, right);
    println!("4. swap_vars!(left, right) 再交换回来: left = {left}, right = {right}");
    assert_eq!((left, right), (1, 2));
    assert_eq!(tmp, 99);
    println!("断言全部通过");
}
