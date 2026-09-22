// 来源：languages/rs/ph07-trait-generics/exercises/README.md 练习 4（用 impl Trait 改写返回迭代器的函数）
// 说明：impl Iterator<Item = ...> 隐藏 filter/map 链的具体类型，调用者只依赖 Iterator 契约
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc sol-04-impl-iterator.rs -o /tmp/sol04
// 运行：/tmp/sol04
// 验证状态：已验证（编译零警告，输出符合预期）

// 偶数的平方：u64 防止 limit 大时 u32 溢出
// 不用 impl Trait 的话，返回类型是 Map<Filter<RangeInclusive<u32>, ...>, ...>——无法手写
fn evens_squared(limit: u32) -> impl Iterator<Item = u64> {
    (0..=limit)
        .filter(|n| n % 2 == 0)
        .map(|n| u64::from(n) * u64::from(n))
}

// base 在 [1..=limit] 内的所有倍数
fn multiples_of(base: u32, limit: u32) -> impl Iterator<Item = u32> {
    (1..=limit).filter(move |n| n % base == 0)
}

fn main() {
    let evens: Vec<u64> = evens_squared(10).collect();
    println!("evens_squared(10): {:?}", evens);

    let multiples: Vec<u32> = multiples_of(3, 10).collect();
    println!("multiples_of(3, 10): {:?}", multiples);

    // 不透明类型仍然支持 Iterator 的全部适配器
    let total: u64 = evens_squared(10).sum();
    println!("sum of evens_squared(10): {total}");
}
