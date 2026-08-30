// examples/pub-api/src/lib.rs —— 库 crate 公开面设计：pub 模块 / 私有模块 / pub use 重导出
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 2
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/pub-api/ 目录内执行）
// 运行：cargo run
// 验证状态：已验证（rustc 1.92.0）

pub mod account;          // 公开模块：外部可见
mod audit;                // 私有模块：外部不可见，即使其中函数是 pub
pub use account::Account; // 重导出：外部直接用 pub_api::Account
