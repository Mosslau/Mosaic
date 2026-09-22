// 来源：languages/rs/ph07-trait-generics/exercises/README.md 练习 5（自定义 PartialEq 与 Hash 的一致性）
// 说明：CaseInsensitiveKey 忽略大小写比较与哈希——PartialEq 与 Hash 用同一套判定逻辑（转小写），保证一致性
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc sol-05-case-insensitive-key.rs -o /tmp/sol05
// 运行：/tmp/sol05
// 验证状态：已验证（编译零警告，无裸 unwrap，输出符合预期）

use std::collections::HashMap;
use std::hash::{Hash, Hasher};

// 比较与哈希都忽略大小写："Info" == "info" == "INFO"
#[derive(Debug, Clone)]
struct CaseInsensitiveKey(String);

impl PartialEq for CaseInsensitiveKey {
    fn eq(&self, other: &Self) -> bool {
        self.0.to_lowercase() == other.0.to_lowercase()
    }
}

impl Eq for CaseInsensitiveKey {}

impl Hash for CaseInsensitiveKey {
    fn hash<H: Hasher>(&self, state: &mut H) {
        // 关键：哈希用与 eq 相同的判定逻辑（转小写），保证"相等即同哈希"
        self.0.to_lowercase().hash(state);
    }
}

fn main() {
    let mut counts: HashMap<CaseInsensitiveKey, u64> = HashMap::new();

    // 同义的三种大小写应聚合到同一个 key
    *counts.entry(CaseInsensitiveKey(String::from("INFO"))).or_insert(0) += 1;
    *counts.entry(CaseInsensitiveKey(String::from("info"))).or_insert(0) += 1;
    *counts.entry(CaseInsensitiveKey(String::from("Warn"))).or_insert(0) += 1;

    println!("distinct keys: {}", counts.len()); // 2（info 合并、warn 独立）

    // 三种大小写查询命中同一个 key
    for probe in ["INFO", "info", "Info"] {
        match counts.get(&CaseInsensitiveKey(String::from(probe))) {
            Some(n) => println!("query {probe:?} -> {n}"),
            None => println!("query {probe:?} -> miss"),
        }
    }
}
