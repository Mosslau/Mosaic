// 来源：languages/rs/ph07-trait-generics/07-trait-generics.md 第 6 章示例 4
// 说明：impl Trait 返回位置——用 impl Iterator 隐藏迭代器链的具体类型，用 impl Fn 返回闭包
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc ex04-impl-trait.rs -o /tmp/ex04
// 运行：/tmp/ex04
// 验证状态：已验证（编译零警告，输出符合预期）

// 返回迭代器：隐藏 (0..=limit).filter(...) 的具体类型
fn range_evens(limit: u32) -> impl Iterator<Item = u32> {
    (0..=limit).filter(|n| n % 2 == 0)
}

// 返回闭包：make_adder(5) 得到一个"加 5"的函数
fn make_adder(base: i32) -> impl Fn(i32) -> i32 {
    move |x| x + base
}

fn main() {
    let evens: Vec<u32> = range_evens(10).collect();
    println!("{:?}", evens); // [0, 2, 4, 6, 8, 10]

    let add5 = make_adder(5);
    println!("add5(37) = {}", add5(37)); // 42
}
