// exercises/sol-05-workspace/crates/word-count-cli/src/main.rs —— 练习 5 参考实现：二进制 crate
// 通过 path 依赖 word-count-core 统计单词数
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build --workspace（在 sol-05-workspace/ 目录内执行）
// 运行：cargo run -p word-count-cli
// 验证状态：已验证（rustc 1.92.0）

use word_count_core::count_words;

fn main() {
    let text = "module system cargo workspace path dependency unit test";
    println!("单词数: {}", count_words(text));
}
