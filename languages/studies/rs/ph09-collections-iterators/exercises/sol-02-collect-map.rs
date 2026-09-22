// 来源：languages/rs/ph09-collections-iterators/exercises/README.md 练习 2
// 说明：练习 collect 到 Vec 和 HashMap——分词、长度映射、entry API 词频统计、按词频降序输出
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-02-collect-map.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;

fn main() {
    let text = "the quick brown fox jumps over the lazy dog the fox";

    // 1) collect 到 Vec：分词（目标类型由 let 标注决定）
    let words: Vec<&str> = text.split_whitespace().collect();

    // 2) (键, 值) 对组成的迭代器可以直接 collect 到 HashMap
    let lengths: HashMap<&str, usize> = words.iter().map(|w| (*w, w.len())).collect();
    println!("lengths: {lengths:?}");

    // 3) 词频统计：重复键不能裸 collect（后者会覆盖），用 entry API 累加
    let mut freq: HashMap<&str, u32> = HashMap::new();
    for w in words {
        *freq.entry(w).or_insert(0) += 1;
    }

    // 4) 按词频降序输出：HashMap -> 迭代器 -> 可排序 Vec，再 sort_by 降序
    let mut ranking: Vec<(&str, u32)> = freq.into_iter().collect();
    ranking.sort_by(|a, b| b.1.cmp(&a.1));
    for (word, count) in &ranking {
        println!("{word}: {count}");
    }
}
