// examples/pub-api/src/main.rs —— 与 lib.rs 是不同 crate：只能用公开 API
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 2
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/pub-api/ 目录内执行）
// 运行：cargo run
// 验证状态：已验证（rustc 1.92.0）

use pub_api::Account;

fn main() {
    let mut acc = Account::open(42);
    acc.deposit(100).expect("存款不应失败");
    println!("id={}, balance={}", acc.id, acc.balance());
    // 以下都无法编译：acc.secret / acc.set_secret(...) 是 pub(crate)，对另一个
    // crate 不可见（E0616/E0624）；acc.balance 是私有字段（E0616）。
}
