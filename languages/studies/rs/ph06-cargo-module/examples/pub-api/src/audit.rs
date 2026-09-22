// examples/pub-api/src/audit.rs —— 私有模块：对 account 可见，对外部 crate 不可见
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 2
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/pub-api/ 目录内执行）
// 运行：cargo run
// 验证状态：已验证（rustc 1.92.0）

pub fn log(msg: String) {
    println!("[audit] {}", msg);
}
