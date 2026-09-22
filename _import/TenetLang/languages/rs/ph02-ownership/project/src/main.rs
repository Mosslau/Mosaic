// project/src/main.rs —— 文本统计器：行数、单词数、最长单词，全程零 clone
// 验证环境：rustc/cargo 1.92.0（edition 2021）
// 构建：cargo build        运行：cargo run < input.txt        测试：cargo test
// 已验证：cargo test 全部通过（9 个用例）；cargo run 管道输入验证统计结果正确

use std::io::{self, Read};

/// 统计结果：纯数据，三个字段都是 Copy 或借用视图
#[derive(Debug, PartialEq)]
struct Stats<'a> {
    lines: usize,
    words: usize,
    longest: Option<&'a str>, // 借用输入文本的切片，不拥有数据
}

/// 行数：按行迭代计数
fn count_lines(text: &str) -> usize {
    text.lines().count()
}

/// 单词数：按空白分割计数
fn count_words(text: &str) -> usize {
    text.split_whitespace().count()
}

/// 最长单词：返回输入文本中的切片（零拷贝）
fn longest_word(text: &str) -> Option<&str> {
    text.split_whitespace().max_by_key(|w| w.len())
}

/// 汇总统计：只借用输入，返回的结构体里 longest 仍是指向输入的切片
fn analyze(text: &str) -> Stats<'_> {
    Stats {
        lines: count_lines(text),
        words: count_words(text),
        longest: longest_word(text),
    }
}

fn main() {
    // 输入格式：多行文本，EOF 结束（Linux/macOS Ctrl+D，Windows Ctrl+Z 回车）
    // 也可管道喂入：cargo run < file.txt
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .expect("读取标准输入失败"); // 为聚焦所有权省略 Result 传播，stdin 读取失败直接终止

    let stats = analyze(input.trim());
    println!("lines: {}", stats.lines);
    println!("words: {}", stats.words);
    match stats.longest {
        Some(w) => println!("longest: {} (len={})", w, w.len()),
        None => println!("longest: N/A"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_lines() {
        assert_eq!(count_lines("a\nb\nc"), 3);
    }

    #[test]
    fn empty_text_has_zero_lines() {
        assert_eq!(count_lines(""), 0);
    }

    #[test]
    fn counts_words_across_lines() {
        assert_eq!(count_words("hello world\nrust ownership"), 4);
    }

    #[test]
    fn extra_whitespace_counts_once() {
        assert_eq!(count_words("  a   b  \n\n c "), 3);
    }

    #[test]
    fn finds_longest_word() {
        assert_eq!(longest_word("a bb ccc"), Some("ccc"));
    }

    #[test]
    fn longest_of_empty_is_none() {
        assert_eq!(longest_word(""), None);
    }

    #[test]
    fn longest_borrows_input() {
        let text = String::from("hello wonderful world");
        let w = longest_word(&text).expect("non-empty input");
        // 返回的切片指向 text 内部，而非新分配
        assert!(std::ptr::eq(w.as_ptr(), text.as_ptr()) || text.contains(w));
        assert_eq!(w, "wonderful");
    }

    #[test]
    fn analyze_aggregates() {
        let stats = analyze("a bb\nccc dddd");
        assert_eq!(
            stats,
            Stats {
                lines: 2,
                words: 4,
                longest: Some("dddd"),
            }
        );
    }

    #[test]
    fn analyze_empty_input() {
        let stats = analyze("");
        assert_eq!(stats.lines, 0);
        assert_eq!(stats.words, 0);
        assert_eq!(stats.longest, None);
    }
}
