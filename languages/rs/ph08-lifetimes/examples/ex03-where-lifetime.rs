// 来源：languages/rs/ph08-lifetimes/08-lifetimes.md 第 6 章示例 3
// 说明：生命周期 + 泛型组合——'a: 'b 生命周期约束与 T: Display trait bound 同处 where 子句
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex03-where-lifetime.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告，输出符合预期）

use std::fmt::Display;

// 'a: 'b（'a 不短于 'b）+ T: Display：两类约束同处 where
// 为什么需要 'a: 'b：x 是 &'a str，返回值是 &'b str（更短）；
// 只有证明 'a 不短于 'b，编译器才允许把 x 的引用收缩成 &'b str 返回
fn choose_longer<'a, 'b, T>(x: &'a str, y: &'b str, tag: T) -> &'b str
where
    'a: 'b,
    T: Display,
{
    println!("tag: {tag}");
    if x.len() >= y.len() { x } else { y }
}

fn main() {
    let x = String::from("rust");   // 外层作用域：x 活得更久
    let result;
    {
        let y = String::from("go"); // 内层作用域：y 活得更短（'b）
        result = choose_longer(&x, &y, "compare");
        println!("inside: {}", result); // 此时 y 还活着，可以用
    }
    // println!("outside: {}", result); // 若取消注释：E0597
    // result 绑定的是较短的 'b（y 的生命周期），y 被 drop 后不可再使用
    println!("done");
}
