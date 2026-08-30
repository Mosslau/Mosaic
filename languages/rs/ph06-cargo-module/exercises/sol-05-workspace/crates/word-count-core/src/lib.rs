// exercises/sol-05-workspace/crates/word-count-core/src/lib.rs —— 练习 5 参考实现：库 crate
// 按空白分词统计单词数，跳过空串
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build --workspace（在 sol-05-workspace/ 目录内执行）
// 测试：cargo test -p word-count-core
// 验证状态：已验证（rustc 1.92.0）

pub fn count_words(text: &str) -> usize {
    text.split_whitespace().count()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normal_text() {
        assert_eq!(count_words("hello world rust"), 3);
    }

    #[test]
    fn multiple_whitespace_merged() {
        assert_eq!(count_words("  hello\t\tworld \n rust  "), 3);
    }

    #[test]
    fn empty_text() {
        assert_eq!(count_words(""), 0);
        assert_eq!(count_words("   \n\t  "), 0);
    }
}
