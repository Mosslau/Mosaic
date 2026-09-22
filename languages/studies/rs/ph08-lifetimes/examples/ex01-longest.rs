// 来源：languages/rs/ph08-lifetimes/08-lifetimes.md 第 6 章示例 1
// 说明：为返回引用的函数添加生命周期——两个输入 + 一个输出时省略规则失效（E0106），必须显式标注 <'a>
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex01-longest.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告，输出符合预期）

// 返回较长字符串的引用：输出绑定到输入 'a
// 去掉 <'a> 写成 fn longest(x: &str, y: &str) -> &str 会报 E0106：
// 省略规则第 2 条只处理"一个输入"，两个输入时无法决定输出归属
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}

fn main() {
    let s1 = String::from("rust");
    let s2 = String::from("go");
    let result = longest(&s1, &s2);
    println!("longer: {}", result); // longer: rust

    // 返回值绑定两个输入中较短的生命周期：tmp 先被 drop 就不能再用 result
    let r;
    {
        let tmp = String::from("temporary");
        r = longest(&s1, &tmp);
        println!("inside: {}", r); // 仍在 tmp 存活期内，合法
    }
    // println!("{}", r); // 若取消注释：E0597，r 借用了 tmp，而 tmp 已 drop
}
