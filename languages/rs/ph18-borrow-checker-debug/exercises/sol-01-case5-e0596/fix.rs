// 修复版（与同目录 error.rs 对照）。把绑定声明为 mut 即可。
// 对照启示：E0596 的报错会直接给出 "help: consider changing this to be mutable"，
//           这类「编译器直接给出修法」的错误与 E0502/E0505 等「需要重构」的错误要分开对待。
// 验证：rustc --edition 2021 fix.rs && ./fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    let mut counter = 0; // 声明可变
    let r = &mut counter; // 允许
    *r += 1;
    println!("{r}");
}
