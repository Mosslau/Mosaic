// 来源：languages/rs/ph08-lifetimes/exercises/README.md 练习 1
// 说明：为返回引用的函数添加生命周期；对比"输出绑定所有输入"与"输出只绑定一个输入"
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-01-add-lifetime.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告，输出符合预期）

// 修复 E0106：两个输入 + 一个输出，省略规则失效，显式标注 <'a>
// 'a 取两个输入中较短的生命周期——最保守、无论如何都安全
fn longer<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}

// 输出只绑定第一个输入：y 的生命周期独立（省略规则第 1 条，各输入独立），与返回值无关
// 因此返回值只要求 x 活着，y 先 drop 也无所谓
fn first<'a>(x: &'a str, y: &str) -> &'a str {
    // y 仅用于比较，不影响返回值的归属
    if y.len() > x.len() {
        println!("note: second input is longer, still returning first");
    }
    x
}

fn main() {
    let s1 = String::from("alpha");

    // first：返回值只绑定 s1，s2 drop 后仍然合法
    let r;
    {
        let s2 = String::from("b");
        r = first(&s1, &s2);
    }
    println!("first: {r}"); // alpha —— 若用 longer 这里会报 E0597

    // longer：返回值绑定两者中较短者，只能用在 s2 存活期内
    {
        let s2 = String::from("b");
        let l = longer(&s1, &s2);
        println!("longer: {l}"); // alpha
    }
    // println!("{l}"); // 故意不通过编译：演示 E0597，l 借用了已 drop 的 s2，请勿取消注释指望 rustc 通过
}
