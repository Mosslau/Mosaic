// 来源：languages/rs/ph07-trait-generics/exercises/README.md 练习 2（把重复函数改造成泛型函数）
// 说明：max_i32/max_f64/max_char 合并为一个 largest<T>，最小 bound 是 PartialOrd + Copy（f64 只有 PartialOrd 没有 Ord）
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc sol-02-largest-generic.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告，无 unwrap/expect，输出符合预期）

// 最小必要 bound：PartialOrd（比较大小）+ Copy（从切片取出 owned 值）
// 不能用 Ord——f64 只有 PartialOrd（NaN 破坏了全序）
fn largest<T: PartialOrd + Copy>(items: &[T]) -> Option<T> {
    let mut result = *items.first()?;
    for &item in items {
        if item > result {
            result = item;
        }
    }
    Some(result)
}

fn main() {
    let ints = [3i32, 9, 5, 7];
    let floats = [1.5f64, -2.0, 3.25];
    let chars = ['a', 'z', 'm'];
    let empty: [i32; 0] = [];

    // 用 match 处理 Option，不用 unwrap
    match largest(&ints) {
        Some(v) => println!("largest i32: {v}"),
        None => println!("largest i32: None"),
    }
    match largest(&floats) {
        Some(v) => println!("largest f64: {v}"),
        None => println!("largest f64: None"),
    }
    match largest(&chars) {
        Some(v) => println!("largest char: {v}"),
        None => println!("largest char: None"),
    }
    match largest(&empty) {
        Some(v) => println!("largest empty: {v}"),
        None => println!("largest empty: None"),
    }
}
