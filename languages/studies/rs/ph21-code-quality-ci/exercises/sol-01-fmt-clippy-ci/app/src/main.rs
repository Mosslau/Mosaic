//! app —— sol-01 的示例成员 crate（质量门禁的干净基线）。
//!
//! 功能：把一段文本按行拆成单词并统计词频，作为「CI 门禁要守住的普通代码」。

use std::collections::BTreeMap;

/// 把文本按空白切词并统计词频；大小写不敏感。
fn word_freq(text: &str) -> BTreeMap<String, usize> {
    let mut freq: BTreeMap<String, usize> = BTreeMap::new();
    for word in text.split_whitespace() {
        let key = word.to_lowercase();
        *freq.entry(key).or_insert(0) += 1;
    }
    freq
}

/// 把词频表渲染成 `word: count` 行。
fn render(freq: &BTreeMap<String, usize>) -> String {
    freq.iter()
        .map(|(w, n)| format!("{w}: {n}"))
        .collect::<Vec<_>>()
        .join("\n")
}

fn main() {
    let text = "rustfmt clippy cargo rustfmt";
    println!("{}", render(&word_freq(text)));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_words_case_insensitively() {
        let f = word_freq("Rust rust RUST");
        assert_eq!(f.get("rust"), Some(&3));
    }

    #[test]
    fn empty_text_has_no_words() {
        assert!(word_freq("   \n  ").is_empty());
    }

    #[test]
    fn render_is_sorted_and_colon_separated() {
        let f = word_freq("b a");
        assert_eq!(render(&f), "a: 1\nb: 1");
    }
}
