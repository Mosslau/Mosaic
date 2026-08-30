// exercises/sol-05-config-extend.rs —— 练习 5 参考实现：扩展配置解析器
// 来源：exercises/README.md 练习 5（基于第 6 章示例 4 扩展 host / max_connections）
// 验证环境：rustc 1.92.0
// 编译：rustc sol-05-config-extend.rs -o /tmp/sol-05-config-extend
// 运行：/tmp/sol-05-config-extend
// 验证状态：已验证（rustc 1.92.0）

use std::collections::HashMap;

#[derive(Debug, PartialEq)]
struct Config {
    host: String,
    port: u16,
    max_connections: u32,
    timeout_secs: u32,
    debug_mode: bool,
    log_level: String,
}

/// 数字字段解析：缺失配错误、非法配错误，错误消息都带字段名
fn parse_u16(raw: Option<&String>, field: &str) -> Result<u16, String> {
    raw.ok_or_else(|| format!("missing value for field: {}", field)).and_then(|s| {
        s.parse::<u16>()
            .map_err(|e| format!("invalid number for field {}: {}", field, e))
    })
}

/// 布尔字段解析：true/false 之外接受 1/0/yes/no，缺失默认 false
fn parse_bool(raw: Option<&String>, field: &str) -> Result<bool, String> {
    match raw.map(|s| s.as_str()) {
        Some("true") | Some("1") | Some("yes") => Ok(true),
        Some("false") | Some("0") | Some("no") => Ok(false),
        Some(other) => Err(format!("invalid bool for field {}: '{}'", field, other)),
        None => Ok(false),
    }
}

/// 用 `?` 串联各字段解析，错误统一带字段名
fn parse_config(raw: &HashMap<String, String>) -> Result<Config, String> {
    // host：必需字段，先取再校验非空
    let host = raw
        .get("host")
        .ok_or_else(|| "missing value for field: host".to_string())?
        .trim()
        .to_string();
    if host.is_empty() {
        return Err("invalid host: must not be empty".to_string());
    }

    let port = parse_u16(raw.get("port"), "port")?;
    if port == 0 {
        return Err("invalid port: port cannot be 0".to_string());
    }

    let max_connections = parse_u16(raw.get("max_connections"), "max_connections")? as u32;
    if max_connections == 0 {
        return Err("invalid max_connections: must be > 0".to_string());
    }

    let timeout_secs = parse_u16(raw.get("timeout"), "timeout")? as u32;
    let debug_mode = parse_bool(raw.get("debug"), "debug")?;
    let log_level = raw
        .get("log_level")
        .cloned()
        .unwrap_or_else(|| "info".to_string());

    Ok(Config { host, port, max_connections, timeout_secs, debug_mode, log_level })
}

fn main() {
    // 全部合法：输出完整 Config
    let mut raw = HashMap::new();
    raw.insert("host".to_string(), "localhost".to_string());
    raw.insert("port".to_string(), "8080".to_string());
    raw.insert("max_connections".to_string(), "200".to_string());
    raw.insert("timeout".to_string(), "30".to_string());
    raw.insert("debug".to_string(), "true".to_string());
    println!("valid: {:?}", parse_config(&raw));

    // 缺必需字段 host
    let mut incomplete = HashMap::new();
    incomplete.insert("port".to_string(), "8080".to_string());
    println!("missing host: {:?}", parse_config(&incomplete));

    // max_connections = 0 校验失败
    let mut bad = HashMap::new();
    bad.insert("host".to_string(), "localhost".to_string());
    bad.insert("port".to_string(), "8080".to_string());
    bad.insert("max_connections".to_string(), "0".to_string());
    println!("max_connections=0: {:?}", parse_config(&bad));
}
