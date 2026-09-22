// project/src/lib.rs —— 配置解析器核心库
// 来源：project/config-parser（roadmap ph04 推荐项目「配置解析器」）
// 说明：读取端口、超时、开关项，输出结构化 Config 或带字段名的明确错误
// 验证环境：rustc 1.92.0（cargo 1.92.0），edition 2021
// 编译：cargo build
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use std::collections::HashMap;
use std::fmt;

/// 解析出的结构化配置
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub port: u16,
    pub timeout_secs: u32,
    pub debug: bool,
    pub log_level: String,
}

/// 配置解析错误：每个变体都携带字段名，错误消息可直接展示给用户
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConfigError {
    /// 必需字段缺失，如 `MissingField("port")`
    MissingField(&'static str),
    /// 某一行不是 `key=value` 格式
    InvalidLine(String),
    /// 数字字段解析失败，如 `timeout=abc`
    InvalidNumber { field: &'static str, raw: String, detail: String },
    /// 布尔字段值非法，如 `debug=maybe`
    InvalidBool { field: &'static str, raw: String },
    /// 配置里出现未知字段（拼写错误即时暴露）
    UnknownKey(String),
    /// 语义校验失败，如 `port=0`
    InvalidValue { field: &'static str, message: String },
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ConfigError::MissingField(field) => write!(f, "缺少必需字段: {field}"),
            ConfigError::InvalidLine(line) => {
                write!(f, "行格式非法（应为 key=value）: {line:?}")
            }
            ConfigError::InvalidNumber { field, raw, detail } => {
                write!(f, "字段 {field} 的值 {raw:?} 不是合法数字: {detail}")
            }
            ConfigError::InvalidBool { field, raw } => {
                write!(f, "字段 {field} 的值 {raw:?} 不是合法布尔值（接受 true/false/1/0/yes/no）")
            }
            ConfigError::UnknownKey(key) => write!(f, "未知配置字段: {key}"),
            ConfigError::InvalidValue { field, message } => {
                write!(f, "字段 {field} 校验失败: {message}")
            }
        }
    }
}

impl std::error::Error for ConfigError {}

/// 已知字段白名单：解析时发现不在表内的 key 即报 `UnknownKey`
const KNOWN_FIELDS: [&str; 4] = ["port", "timeout", "debug", "log_level"];

/// 把一行 `key=value` 拆成键值对，值会做 trim
fn parse_line(line: &str) -> Result<(String, String), ConfigError> {
    let Some((key, value)) = line.split_once('=') else {
        return Err(ConfigError::InvalidLine(line.to_string()));
    };
    let key = key.trim();
    if key.is_empty() {
        return Err(ConfigError::InvalidLine(line.to_string()));
    }
    Ok((key.to_string(), value.trim().to_string()))
}

/// 把多行配置文本解析为结构化配置。空行与 `#` 开头的注释行被跳过。
pub fn parse_config_lines(lines: &[&str]) -> Result<Config, ConfigError> {
    let mut raw = HashMap::new();
    for line in lines {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (key, value) = parse_line(line)?;
        raw.insert(key, value);
    }
    Config::from_pairs(&raw)
}

impl Config {
    /// 从键值对构建配置：校验未知字段、必需字段与取值语义
    pub fn from_pairs(raw: &HashMap<String, String>) -> Result<Config, ConfigError> {
        for key in raw.keys() {
            if !KNOWN_FIELDS.contains(&key.as_str()) {
                return Err(ConfigError::UnknownKey(key.clone()));
            }
        }

        // port：必需字段，先取再校验取值
        let port = match raw.get("port") {
            Some(v) => parse_u16(v, "port")?,
            None => return Err(ConfigError::MissingField("port")),
        };
        if port == 0 {
            return Err(ConfigError::InvalidValue {
                field: "port",
                message: "端口必须在 1~65535 之间".to_string(),
            });
        }

        // timeout：可选，默认 30 秒
        let timeout_secs = match raw.get("timeout") {
            Some(v) => parse_u16(v, "timeout")? as u32,
            None => 30,
        };

        // debug：可选开关，默认 false
        let debug = match raw.get("debug") {
            Some(v) => parse_bool(v, "debug")?,
            None => false,
        };

        // log_level：可选字符串，默认 "info"
        let log_level = raw
            .get("log_level")
            .cloned()
            .unwrap_or_else(|| "info".to_string());

        Ok(Config { port, timeout_secs, debug, log_level })
    }
}

/// 解析 u16 数字字段，失败报 `InvalidNumber`（带字段名与解析原因）
fn parse_u16(value: &str, field: &'static str) -> Result<u16, ConfigError> {
    value.parse::<u16>().map_err(|e| ConfigError::InvalidNumber {
        field,
        raw: value.to_string(),
        detail: e.to_string(),
    })
}

/// 解析布尔字段：接受 true/false/1/0/yes/no，其他值报 `InvalidBool`
fn parse_bool(value: &str, field: &'static str) -> Result<bool, ConfigError> {
    match value {
        "true" | "1" | "yes" => Ok(true),
        "false" | "0" | "no" => Ok(false),
        other => Err(ConfigError::InvalidBool { field, raw: other.to_string() }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 把文本按行切片交给解析器（测试辅助）
    fn parse(text: &str) -> Result<Config, ConfigError> {
        let lines: Vec<&str> = text.lines().collect();
        parse_config_lines(&lines)
    }

    /// 应解析成功的辅助：失败即 panic 并打印错误（仅测试用）
    fn must_parse(text: &str) -> Config {
        match parse(text) {
            Ok(cfg) => cfg,
            Err(e) => panic!("应解析成功，实际失败: {e}"),
        }
    }

    #[test]
    fn valid_config_parses_all_fields() {
        let cfg = must_parse("port=8080\ntimeout=30\ndebug=true\nlog_level=debug\n");
        assert_eq!(cfg.port, 8080);
        assert_eq!(cfg.timeout_secs, 30);
        assert!(cfg.debug);
        assert_eq!(cfg.log_level, "debug");
    }

    #[test]
    fn comments_and_blank_lines_are_skipped() {
        let cfg = must_parse("# demo 配置\n\nport=7000\n\n# 下面这行不生效\n");
        assert_eq!(cfg.port, 7000);
        assert_eq!(cfg.timeout_secs, 30); // 未设置，取默认值
        assert!(!cfg.debug);
        assert_eq!(cfg.log_level, "info");
    }

    #[test]
    fn defaults_applied_when_optional_missing() {
        let cfg = must_parse("port=8080\n");
        assert_eq!(cfg.timeout_secs, 30);
        assert!(!cfg.debug);
        assert_eq!(cfg.log_level, "info");
    }

    #[test]
    fn missing_port_reports_field_name() {
        match parse("timeout=30\n") {
            Ok(_) => panic!("缺少 port 应解析失败"),
            Err(ConfigError::MissingField("port")) => {}
            Err(e) => panic!("错误类型不符: {e}"),
        }
    }

    #[test]
    fn port_zero_is_rejected() {
        match parse("port=0\n") {
            Ok(_) => panic!("port=0 应被拒绝"),
            Err(ConfigError::InvalidValue { field: "port", .. }) => {}
            Err(e) => panic!("错误类型不符: {e}"),
        }
    }

    #[test]
    fn invalid_port_number_reports_field_and_raw() {
        match parse("port=8080abc\n") {
            Ok(_) => panic!("非法端口应解析失败"),
            Err(ConfigError::InvalidNumber { field: "port", raw, .. }) => {
                assert_eq!(raw, "8080abc");
            }
            Err(e) => panic!("错误类型不符: {e}"),
        }
    }

    #[test]
    fn invalid_timeout_reports_field() {
        match parse("port=8080\ntimeout=abc\n") {
            Ok(_) => panic!("非法 timeout 应解析失败"),
            Err(ConfigError::InvalidNumber { field: "timeout", .. }) => {}
            Err(e) => panic!("错误类型不符: {e}"),
        }
    }

    #[test]
    fn invalid_bool_value_reports_field_and_raw() {
        match parse("port=8080\ndebug=maybe\n") {
            Ok(_) => panic!("非法 bool 应解析失败"),
            Err(ConfigError::InvalidBool { field: "debug", raw }) => {
                assert_eq!(raw, "maybe");
            }
            Err(e) => panic!("错误类型不符: {e}"),
        }
    }

    #[test]
    fn unknown_key_is_rejected() {
        match parse("port=8080\npoet=8081\n") {
            Ok(_) => panic!("未知字段应解析失败"),
            Err(ConfigError::UnknownKey(key)) => assert_eq!(key, "poet"),
            Err(e) => panic!("错误类型不符: {e}"),
        }
    }

    #[test]
    fn malformed_line_is_rejected() {
        match parse("no-equals-here\n") {
            Ok(_) => panic!("缺 = 的行应解析失败"),
            Err(ConfigError::InvalidLine(_)) => {}
            Err(e) => panic!("错误类型不符: {e}"),
        }
    }

    #[test]
    fn bool_accepts_short_forms() {
        let cfg = must_parse("port=8080\ndebug=1\n");
        assert!(cfg.debug);
        let cfg = must_parse("port=8080\ndebug=no\n");
        assert!(!cfg.debug);
    }
}
