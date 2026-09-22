//! 治理前版本（故意带 lint）——仅供演示「质量门禁红→绿」流程，切勿照抄进真实代码。
//!
//! 复现：复制本文件到 src/main.rs，然后 ./scripts/check.sh
//! 预期：clippy 步骤失败（-D warnings），报出以下 lint（本机 cargo/clippy 1.92.0 实测）：
//!   needless_range_loop（style，默认 warn）      —— 手写下标循环
//!   ptr_arg（style，默认 warn）                   —— 参数写 &Vec 而非 &[T]
//!   manual_map（style，默认 warn）                —— 手写 match 当 map
//! 恢复：git checkout -- demo-app/src/main.rs（或从仓库历史恢复全绿版）。
#![allow(dead_code)] // 样例聚焦 lint 治理，忽略死代码告警

use std::collections::HashSet;

/// style：手写下标循环只用来取 words[i] —— 治理成迭代器
pub fn unique_words(records: &[String]) -> usize {
    let mut seen: HashSet<String> = HashSet::new();
    for i in 0..records.len() {
        seen.insert(records[i].to_lowercase());
    }
    seen.len()
}

/// style：参数写 &Vec —— 治理成 &[String]
pub fn count_long(records: &Vec<String>, threshold: usize) -> usize {
    let mut n = 0;
    for i in 0..records.len() {
        if records[i].len() > threshold {
            n += 1;
        }
    }
    n
}

/// style：手写 match 当 map —— 治理成 first().map(...)
pub fn describe_first(records: &[String]) -> Option<String> {
    match records.first() {
        Some(w) => Some(format!("first: {w}")),
        None => None,
    }
}

fn main() {
    let words = vec![String::from("Rust"), String::from("rust"), String::from("clippy")];
    println!("unique={}", unique_words(&words));
    println!("long={}", count_long(&words, 4));
    println!("{:?}", describe_first(&words));
}
