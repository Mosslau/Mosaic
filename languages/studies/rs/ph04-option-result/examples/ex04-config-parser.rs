// examples/ex04-config-parser.rs —— 配置解析器：Option/Result 贯穿 + ? 传播
// 来源：04-option-result.md 第 6 章示例 4
// 验证环境：rustc 1.92.0
// 编译：rustc ex04-config-parser.rs -o /tmp/ex04-config-parser
// 运行：/tmp/ex04-config-parser
// 验证状态：已验证（rustc 1.92.0）

use std::collections::HashMap;

/// 综合运用本阶段知识产出的结构化配置
#[derive(Debug)]
#[allow(dead_code)] // 教学示例：字段可能仅用于 Debug 打印
struct Config {
    port: u16,
    timeout_secs: u32,
    debug_mode: bool,
    log_level: String,
}

/// `Option` + 组合子解析数字字段：`ok_or_else` 给缺失值配错误，`and_then` 串联解析
fn parse_u16(raw: Option<&String>) -> Result<u16, String> {
    raw.ok_or_else(|| "missing value".to_string())
        .and_then(|s| s.parse::<u16>().map_err(|e| format!("invalid number: {}", e)))
}

/// 解析布尔开关：true/false 之外接受 1/0/yes/no，未知值报错，缺失默认 false
fn parse_bool(raw: Option<&String>) -> Result<bool, String> {
    match raw.map(|s| s.as_str()) {
        Some("true") | Some("1") | Some("yes") => Ok(true),
        Some("false") | Some("0") | Some("no") => Ok(false),
        Some(other) => Err(format!("invalid bool: '{}'", other)),
        None => Ok(false),
    }
}

/// 用 `?` 串联各字段解析：任一步失败整条管线短路返回 Err
fn parse_config(raw: &HashMap<String, String>) -> Result<Config, String> {
    let port = parse_u16(raw.get("port"))?;
    let timeout_secs = parse_u16(raw.get("timeout")).map(|v| v as u32)?;
    let debug_mode = parse_bool(raw.get("debug"))?;
    let log_level = raw.get("log_level").cloned().unwrap_or_else(|| "info".to_string());
    if port == 0 {
        return Err("port cannot be 0".to_string());
    }
    Ok(Config { port, timeout_secs, debug_mode, log_level })
}

fn main() {
    let mut raw = HashMap::new();
    raw.insert("port".to_string(), "8080".to_string());
    raw.insert("timeout".to_string(), "30".to_string());
    raw.insert("debug".to_string(), "true".to_string());
    raw.insert("log_level".to_string(), "debug".to_string());
    println!("valid: {:?}", parse_config(&raw));

    // 缺失必需字段 port
    let mut incomplete = HashMap::new();
    incomplete.insert("timeout".to_string(), "10".to_string());
    println!("missing: {:?}", parse_config(&incomplete));
}
