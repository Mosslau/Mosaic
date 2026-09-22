// examples/feat-demo/src/lib.rs —— features 特性开关：纯开关 pretty + 可选依赖 json
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 4
// 验证环境：rustc 1.92.0 + cargo 1.92.0，依赖 serde_json 1.0.108（需网络拉取，可选）
// 编译：cargo build（在 examples/feat-demo/ 目录内执行）
// 运行：cargo run（可用 --no-default-features / --features pretty / --all-features 组合）
// 验证状态：已验证（rustc 1.92.0）

pub fn describe() -> &'static str {
    if cfg!(feature = "pretty") { "feat-demo (pretty)" } else { "feat-demo" }
}

#[cfg(feature = "json")]
pub mod json_util {
    pub fn pretty_print(json: &str) -> serde_json::Result<String> {
        let v: serde_json::Value = serde_json::from_str(json)?;
        serde_json::to_string_pretty(&v)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn describe_default() {
        assert!(describe().starts_with("feat-demo"));
    }

    #[cfg(feature = "json")]
    #[test]
    fn pretty_print_works_when_json_enabled() {
        let pretty = json_util::pretty_print(r#"{"a":1}"#).unwrap();
        assert!(pretty.contains("\n")); // 多行格式化
    }
}
