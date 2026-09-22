//! ex01-fmt-diff —— rustfmt / `cargo fmt --check` 的门禁语义演示（已验证：rustfmt 1.8.0）。
//!
//! 本文件是**治理后**的参考版本（格式规范，`cargo fmt --check` 退出 0）。
//! 治理前版本在同目录 `before/main.rs`（故意未格式化，仅供复制回 `src/` 复现
//! fmt 门禁红/绿两种状态，不会参与本 crate 的任何构建与检查）。
//!
//! 复现步骤（在本 crate 目录内执行）：
//!   # 1. 治理前：把未格式化版本复制回 src
//!   cp before/main.rs src/main.rs
//!   # 2. 门禁变红：--check 打印 diff 并退出 1（实测 exit=1）
//!   cargo fmt --check
//!   # 3. 自动治理：cargo fmt 改写文件
//!   cargo fmt
//!   # 4. 门禁变绿：再查退出 0（实测 exit=0）
//!   cargo fmt --check
//!   # 5. 对照：治理后的文件应与本文件内容一致
//!   #    git diff src/main.rs  （或手动把 src/main.rs 与本文件 diff）

fn main() {
let items = vec!["rustfmt", "clippy", "cargo"];
println!("tools:");
for item in items {
println!("- {}", item);
}
}

fn add(a: i32, b: i32) -> i32 {
a + b
}
