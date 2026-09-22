// examples/ex05-text-stats.rs —— 文本统计器（零 clone 版）：行数、单词数、最长单词
// 验证环境：rustc 1.92.0
// 编译：rustc ex05-text-stats.rs -o ex05
// 运行：./ex05   （输入多行文本后按 Ctrl+D 结束；或管道喂入：printf 'a b\nc\n' | ./ex05）
// 已验证：本环境编译零警告，管道输入 'hello world\nrust ownership\n' 输出 lines: 2 / words: 4 / longest: ownership

use std::io::{self, Read};

fn count_lines(text: &str) -> usize {
    text.lines().count()
}

fn count_words(text: &str) -> usize {
    text.split_whitespace().count()
}

fn longest_word(text: &str) -> Option<&str> {
    text.split_whitespace().max_by_key(|w| w.len())
}

fn main() {
    // 输入格式：多行文本，EOF 结束（Linux/macOS 按 Ctrl+D，Windows 按 Ctrl+Z 后回车）
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .expect("读取标准输入失败"); // 为聚焦所有权省略 Result 传播，stdin 读取失败直接终止

    let text = input.trim();
    println!("lines: {}", count_lines(text));
    println!("words: {}", count_words(text));

    match longest_word(text) {
        Some(w) => println!("longest: {} (len={})", w, w.len()),
        None => println!("longest: N/A"),
    }
}
