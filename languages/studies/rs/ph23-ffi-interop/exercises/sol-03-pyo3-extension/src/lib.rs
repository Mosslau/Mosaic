//! sol-03：把 Rust 函数包装成 Python 扩展（练习 3 参考实现）。
//!
//! 要求回顾：`count_words`（按空白切分计数）与 `top_k_words`（词频 Top-k，
//! 平局按字典序）。空文本返回 0 / 空列表，不 panic、不抛异常。
//!
//! 教学点：核心算法与 pyo3 薄包装同文件分层，导出面只有两个 `#[pyfunction]`。
//! 注意：纯 cdylib 没有 rlib，`cargo test` 无目标可链接（examples/README 质量闸门一节有解释）——
//! 本练习的验证全部落在 Python 冒烟 `smoke_test.py`，这正是「导出库的测试在消费方」的形态。
//! 验证环境：cargo/rustc 1.92.0 + pyo3 0.23.5 + Python 3.13.12，本机实测「已验证」。

use pyo3::prelude::*;
use std::collections::HashMap;

/// 纯 Rust 核心：把文本按空白拆成单词序列。
fn words(text: &str) -> Vec<&str> {
    text.split_whitespace().collect()
}

/// 纯 Rust 核心：统计词频并取 Top-k（平局按字典序）。
fn top_k_words_inner(text: &str, k: usize) -> Vec<(String, usize)> {
    if k == 0 {
        return Vec::new();
    }
    let mut freq: HashMap<&str, usize> = HashMap::new();
    for w in words(text) {
        *freq.entry(w).or_insert(0) += 1;
    }
    let mut entries: Vec<(String, usize)> =
        freq.into_iter().map(|(w, n)| (w.to_string(), n)).collect();
    // 排序规则：频次降序；频次相同按单词升序（字典序）
    entries.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    entries.truncate(k);
    entries
}

/// Python 可见：数单词个数。
#[pyfunction]
fn count_words(text: &str) -> usize {
    words(text).len()
}

/// Python 可见：词频 Top-k，返回 list[tuple[str, int]]。
#[pyfunction]
fn top_k_words(text: &str, k: usize) -> Vec<(String, usize)> {
    top_k_words_inner(text, k)
}

/// 模块初始化。
#[pymodule]
fn sol03_fastwords(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(count_words, m)?)?;
    m.add_function(wrap_pyfunction!(top_k_words, m)?)?;
    Ok(())
}
