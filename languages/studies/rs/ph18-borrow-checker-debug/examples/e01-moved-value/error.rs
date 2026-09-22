// 本文件故意编译失败：期望错误码 E0382（use of moved value）。
// 场景：String 的所有权被 move 到另一个变量之后，原变量仍被使用。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0382]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let title = String::from("hello"); // title 拥有堆上的字符串
    let taken = title; // 所有权 move：从 title 转移到 taken
    println!("长度: {}", title.len()); // E0382：title 已让出所有权，不能再读
    println!("内容: {taken}");
}
