// 02 · 生命周期演示
// 运行：cargo run --bin 02_lifetimes

/// 显式生命周期：返回的引用活得和两个参数中较短的那个一样久。
/// 'a 只是给编译器的名字，运行时零开销。
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}

fn main() {
    println!("== 生命周期：返回引用需要标注 ==");
    let a = String::from("rust");
    let b = String::from("design");
    let r = longest(&a, &b);
    println!("较长的: {r}");

    println!("\n== 悬垂引用被拒绝 ==");
    // 下面的代码如果取消注释，编译会报错：
    // let r;
    // {
    //     let tmp = String::from("dangling");
    //     r = &tmp;   // ❌ tmp 在块结束时释放，r 会悬垂
    // }
    // println!("{r}");
    println!("（demo 中悬垂示例被注释，打开即可看到编译错误）");

    println!("\n== 省略规则：大多数情况不用写 ==");
    let s = String::from("elided");
    let first = first_word(&s);
    println!("第一个词: {first}");
}

/// 省略规则：输入一个 &str，输出 &str 默认绑定到输入的生命周期。
fn first_word(s: &str) -> &str {
    s.split_whitespace().next().unwrap_or("")
}
