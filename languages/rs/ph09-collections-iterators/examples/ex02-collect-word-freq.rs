// 来源：languages/rs/ph09-collections-iterators/09-collections-iterators.md 第 6 章示例 2
// 说明：collect 到 Vec 和 HashMap——分词、长度映射、entry API 词频统计、按词频排序输出
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex02-collect-word-freq.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;

fn main() {
    let text = "the quick brown fox jumps over the lazy dog the fox";

    // collect 到 Vec：分词（split_whitespace 产出 &str 迭代器）
    let words: Vec<&str> = text.split_whitespace().collect();

    // (键, 值) 对组成的迭代器可以直接 collect 到 HashMap：
    // 元素是 (&str, usize)，目标类型 HashMap<&str, usize> 由 let 标注决定
    let lengths: HashMap<&str, usize> = words.iter().map(|w| (*w, w.len())).collect();
    println!("lengths: {lengths:?}");

    // 词频统计：重复键不能裸 collect（后者会覆盖），用 entry API 累加
    let mut freq: HashMap<&str, u32> = HashMap::new();
    for w in words {
        *freq.entry(w).or_insert(0) += 1;
    }

    // 按词频降序输出：HashMap -> 迭代器 -> 可排序的 Vec
    let mut ranking: Vec<(&str, u32)> = freq.into_iter().collect();
    ranking.sort_by(|a, b| b.1.cmp(&a.1));
    for (word, count) in &ranking {
        println!("{word}: {count}");
    }
}
