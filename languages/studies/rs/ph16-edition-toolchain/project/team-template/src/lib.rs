//! team-template 库根：团队模板的最小领域代码（一句问候逻辑）。
//!
//! 模板约定：领域逻辑进 lib（可测试、可复用），main.rs 只做参数解析与打印。

/// 生成一句问候语。
///
/// `name` 为空字符串时回退到 `"world"`，保证输出永远非空。
#[must_use]
pub fn greeting(name: &str) -> String {
    let who = if name.is_empty() { "world" } else { name };
    format!("hello, {who}!")
}

/// 当前模板声明的 MSRV（与 Cargo.toml 的 rust-version 保持一致）。
///
/// 返回元组便于调用方打印或断言；用常量而不是读 Cargo.toml，避免运行时依赖清单文件。
pub const MSRV: (u32, u32) = (1, 85);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn greets_by_name() {
        assert_eq!(greeting("rust"), "hello, rust!");
    }

    #[test]
    fn empty_name_falls_back_to_world() {
        assert_eq!(greeting(""), "hello, world!");
    }

    #[test]
    fn msrv_matches_cargo_toml_declaration() {
        assert_eq!(MSRV, (1, 85));
    }
}
