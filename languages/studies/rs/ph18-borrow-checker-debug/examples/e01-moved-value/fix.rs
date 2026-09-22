// 修复版（与同目录 error.rs 对照，可通过编译并运行）。
// 修复思路：读长度 / 读内容是「只读」操作，用借用即可，所有权留在 title 里。
// 验证：rustc --edition 2021 fix.rs -o /tmp/e01-moved-value-fix && /tmp/e01-moved-value-fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    let title = String::from("hello");
    // 修复 1：直接以借用读属性（&String 自动降级成 &str），不触发 move
    println!("长度: {}", title.len());
    // 修复 2：把读取逻辑放进「按引用收参数」的函数，所有权依旧留在调用方
    let n = byte_len(&title);
    println!("byte_len = {n}，title 还能继续用：{title}");
}

fn byte_len(s: &str) -> usize {
    s.len()
}
