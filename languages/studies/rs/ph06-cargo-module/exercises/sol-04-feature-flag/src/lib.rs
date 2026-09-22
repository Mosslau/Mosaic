// exercises/sol-04-feature-flag/src/lib.rs —— 练习 4 参考实现：features + 可选依赖
// 表格格式化工具库：text 特性输出文本表格，json 特性输出 JSON
// 验证环境：rustc 1.92.0 + cargo 1.92.0，serde_json 1.0.108（可选，需网络拉取）
// 编译：cargo build（在 sol-04-feature-flag/ 目录内执行）
// 运行：cargo run（可用 --no-default-features / --features json / --all-features 组合）
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

pub fn format_table(rows: &[(String, i32)]) -> String {
    let mut out = String::from("name           value\n------------------------\n");
    for (name, value) in rows {
        out.push_str(&format!("{:<15} {:>5}\n", name, value));
    }
    out
}

#[cfg(feature = "json")]
pub fn format_json(rows: &[(String, i32)]) -> serde_json::Result<String> {
    let arr: Vec<serde_json::Value> = rows
        .iter()
        .map(|(name, value)| serde_json::json!({ "name": name, "value": value }))
        .collect();
    serde_json::to_string_pretty(&arr)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<(String, i32)> {
        vec![("disk".to_string(), 80), ("cpu".to_string(), 12)]
    }

    #[test]
    fn text_table_contains_rows() {
        let table = format_table(&sample());
        assert!(table.contains("disk"));
        assert!(table.contains("80"));
    }

    #[cfg(feature = "json")]
    #[test]
    fn json_output_is_valid() {
        let json = format_json(&sample()).unwrap();
        assert!(json.contains("\"name\": \"disk\""));
        assert!(json.contains("\"value\": 80"));
    }
}
