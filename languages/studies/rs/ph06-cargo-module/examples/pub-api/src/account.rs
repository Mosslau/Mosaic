// examples/pub-api/src/account.rs —— 三层可见性示范：pub 字段 / pub(crate) 字段 / 私有字段
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 2
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/pub-api/ 目录内执行）
// 运行：cargo run
// 验证状态：已验证（rustc 1.92.0）

use crate::audit;

#[allow(dead_code)] // 演示用：secret/set_secret 仅供 crate 内部
pub struct Account {
    pub id: u32,               // 完全公开
    pub(crate) secret: String, // 仅本 crate 可见
    balance: i64,              // 私有：仅本模块可见
}

impl Account {
    pub fn open(id: u32) -> Account {
        Account { id, secret: String::new(), balance: 0 }
    }
    pub fn deposit(&mut self, amount: i64) -> Result<(), String> {
        if amount <= 0 { return Err(String::from("金额必须为正")); }
        self.balance += amount;
        audit::log(format!("deposit {} -> {}", self.id, amount));
        Ok(())
    }
    pub fn balance(&self) -> i64 { self.balance }
    #[allow(dead_code)] // pub(crate) 方法：仅供 crate 内部（见 lib.rs 注释说明）
    pub(crate) fn set_secret(&mut self, secret: String) { self.secret = secret; }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn open_and_deposit() {
        let mut acc = Account::open(1);
        assert_eq!(acc.id, 1);
        assert_eq!(acc.balance(), 0);
        acc.deposit(100).unwrap();
        assert_eq!(acc.balance(), 100);
    }

    #[test]
    fn deposit_rejects_non_positive() {
        let mut acc = Account::open(2);
        assert!(acc.deposit(0).is_err());
        assert!(acc.deposit(-5).is_err());
        assert_eq!(acc.balance(), 0);
    }

    #[test]
    fn pub_crate_field_visible_in_crate() {
        let mut acc = Account::open(3);
        acc.set_secret("hunter2".to_string());
        assert_eq!(acc.secret, "hunter2"); // 同一 crate 内可访问 pub(crate) 字段
    }
}
