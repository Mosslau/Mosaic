// 来源：languages/rs/ph07-trait-generics/exercises/README.md 练习 3（where 子句约束复杂泛型）
// 说明：count_by 三个泛型参数（T/K/F），约束全部收进 where 子句保持签名可读
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc sol-03-count-by.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;
use std::hash::Hash;

// 约束：F 是 &T -> K 的闭包；K 能作为 HashMap 的 key（Eq + Hash）
// 三组约束全部进 where 子句，签名行保持短
fn count_by<T, K, F>(items: &[T], key_fn: F) -> HashMap<K, usize>
where
    K: Eq + Hash,
    F: Fn(&T) -> K,
{
    let mut counts: HashMap<K, usize> = HashMap::new();
    for item in items {
        *counts.entry(key_fn(item)).or_insert(0) += 1;
    }
    counts
}

fn main() {
    // 用法 1：对字符串切片按原值计数
    let levels = ["INFO", "WARN", "INFO", "ERROR", "INFO", "WARN"];
    let by_level = count_by(&levels, |s| *s);
    println!("by level: {:?}", by_level);
    match by_level.get("INFO") {
        Some(n) => println!("INFO count: {n}"),
        None => println!("INFO count: 0"),
    }

    // 用法 2：对元组按 level 字段计数
    let records = [
        ("req-a", "INFO"),
        ("req-b", "WARN"),
        ("req-c", "INFO"),
    ];
    let by_record_level = count_by(&records, |(_, level)| *level);
    println!("by record level: {:?}", by_record_level);
}
