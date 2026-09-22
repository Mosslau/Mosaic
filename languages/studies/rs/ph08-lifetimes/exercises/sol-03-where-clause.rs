// 来源：languages/rs/ph08-lifetimes/exercises/README.md 练习 3
// 说明：where 子句同时容纳生命周期约束 'a: 'b 与 trait bound T: Display
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-03-where-clause.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告，输出符合预期）

use std::fmt::Display;

// <> 中只保留参数名，全部约束收进 where：
// - 'a: 'b（'a 不短于 'b）：x 是 &'a str 而返回值是 &'b str（更短），
//   只有证明 'a 不短于 'b，编译器才允许把 x 的引用收缩成 &'b str 返回（协变）
// - T: Display：tag 需要可打印
fn echo_longest<'a, 'b, T>(x: &'a str, y: &'b str, tag: T) -> &'b str
where
    'a: 'b,
    T: Display,
{
    println!("tag: {tag}");
    if x.len() >= y.len() { x } else { y }
}

fn main() {
    let x = String::from("rust");   // 外层作用域：x 活得更久（'a）
    let result;
    {
        let y = String::from("go"); // 内层作用域：y 活得更短（'b）
        result = echo_longest(&x, &y, "compare");
        println!("inside: {result}"); // 返回值绑定 'b，只能用在 y 存活期内
    }
    // println!("outside: {result}"); // 故意不通过编译：演示 E0597，y 已 drop，请勿取消注释指望 rustc 通过
    println!("done");
}
