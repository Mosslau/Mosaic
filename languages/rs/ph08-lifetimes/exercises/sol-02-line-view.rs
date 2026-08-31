// 来源：languages/rs/ph08-lifetimes/exercises/README.md 练习 2
// 说明：持有引用的结构体 LineView<'a>——struct/impl 必须写 <'a>，方法靠省略规则不用写
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-02-line-view.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告，输出符合预期）

// 借用它指向的那行文本：零拷贝，实例不能比原文活得久
struct LineView<'a> {
    text: &'a str,
    number: usize,
}

impl<'a> LineView<'a> {
    fn new(text: &'a str, number: usize) -> Self {
        LineView { text, number }
    }

    // 省略规则第 3 条：&self 的生命周期自动赋给返回值，方法签名无需写 'a
    fn text(&self) -> &str { self.text }
    fn number(&self) -> usize { self.number }

    // 返回该行首个单词；空行返回 ""（'static 字面量，协变收缩为任何生命周期）
    fn first_word(&self) -> &str {
        self.text.split_whitespace().next().unwrap_or("")
    }
}

fn main() {
    let log = String::from("INFO boot ok\nWARN disk almost full\nERROR disk full\n");
    for (i, line) in log.lines().enumerate() {
        let view = LineView::new(line, i + 1);
        println!("line {} [{}]: first word = {}", view.number(), view.text(), view.first_word());
    }
    // 所有 LineView 实例与 log 同生共死：log drop 后任何 view 都不可再用
}
