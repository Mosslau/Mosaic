// 修复版（与同目录 error.rs 对照）：返回值改成拥有所有权的 String。
// 「拼接出新内容」意味着要造一段不属于任何输入的新数据 —— 它没有现成的借用来源，
// 把所有权交回给调用方是唯一干净的写法（引入拥有数据，见主文档 3.9）。
// 验证：rustc --edition 2021 fix.rs -o /tmp/c03-return-local-ref-fix && /tmp/c03-return-local-ref-fix（已验证：rustc 1.92.0 / macOS arm64）。
fn best_of(a: &str, b: &str) -> String {
    format!("{a}|{b}") // 返回拥有值，调用方负责其生命周期
}

fn main() {
    let s = best_of("x", "y");
    println!("{s}");
}
