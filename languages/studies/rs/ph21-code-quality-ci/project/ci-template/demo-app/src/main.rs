//! demo-app —— ci-template 的示例 crate（治理后全绿基线）。
//!
//! 它代表「模板要守护的那类代码」的最小样本：一个能测试、能 lint 的简单处理逻辑，
//! 附带单元测试。换成真实 crate 时保留 src/main.rs + #[cfg(test)] 结构即可。
//!
//! 验证命令（在 ci-template 根）：
//!   ./scripts/check.sh          # 本地门禁：fmt → clippy -D warnings → test

/// 计算文本里出现的不同单词数（空白切分、大小写折叠）。
pub fn unique_words(text: &str) -> usize {
    text.split_whitespace()
        .map(|w| w.to_lowercase())
        .collect::<std::collections::HashSet<_>>()
        .len()
}

/// 输出一段统计摘要。
pub fn summarize(text: &str) -> String {
    let words = unique_words(text);
    format!("unique words: {words}")
}

fn main() {
    println!("{}", summarize("Rust clippy rustfmt cargo Rust"));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unique_words_folds_case() {
        assert_eq!(unique_words("Rust rust RUST"), 1);
    }

    #[test]
    fn unique_words_counts_distinct() {
        assert_eq!(unique_words("a b c a"), 3);
    }

    #[test]
    fn summarize_renders_count() {
        assert_eq!(summarize("x y"), "unique words: 2");
    }
}
