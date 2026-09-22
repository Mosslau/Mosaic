// 来源：languages/rs/ph11-error-handling/exercises/README.md 练习 5
// 说明：为解析模块补充正常路径和异常路径测试——用 rustc --test 直接跑（无需 cargo）：
//       单元测试覆盖正常路径、异常路径、重复 key、panic 契约（#[should_panic]）、
//       Result 返回测试。本文件由测试 harness 驱动，无需 main()。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings --test sol-05-parser-tests.rs -o /tmp/sol05
// 运行：/tmp/sol05
// 验证状态：已验证（编译零警告；测试结果「test result: ok. 6 passed; 0 failed」为实测）

//! 解析模块：把 `key=value` 文本解析成配置表（库代码偏向「具体错误」：纯 std 手写枚举）

use std::collections::HashMap;
use std::fmt;

#[derive(Debug, PartialEq, Eq)]
pub enum ParseError {
    MissingEquals(String), // 缺少 `=` 分隔符（携带整行原文）
    DuplicateKey(String),  // 重复的 key
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ParseError::MissingEquals(line) => write!(f, "缺少 `=` 分隔符: {line:?}"),
            ParseError::DuplicateKey(key) => write!(f, "重复的 key: {key:?}"),
        }
    }
}

impl std::error::Error for ParseError {}

pub fn parse_line(line: &str) -> Result<(String, String), ParseError> {
    line.split_once('=')
        .map(|(k, v)| (k.trim().to_string(), v.trim().to_string()))
        .ok_or_else(|| ParseError::MissingEquals(line.to_string()))
}

pub fn parse_config(text: &str) -> Result<HashMap<String, String>, ParseError> {
    let mut map = HashMap::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue; // 空行在配置文件中合法，跳过
        }
        let (key, value) = parse_line(line)?;
        if map.insert(key.clone(), value).is_some() {
            return Err(ParseError::DuplicateKey(key));
        }
    }
    Ok(map)
}

/// 便捷入口：输入非法时按「契约」panic（调用方保证输入合法时才用它）
pub fn parse_config_checked(text: &str) -> HashMap<String, String> {
    parse_config(text).expect("config text must be valid")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_line_ok() {
        // 正常路径：返回值正确
        assert_eq!(
            parse_line("host = 127.0.0.1").unwrap(),
            ("host".to_string(), "127.0.0.1".to_string())
        );
    }

    #[test]
    fn parse_line_missing_equals() {
        // 异常路径：缺 `=` 报 MissingEquals，错误消息含整行原文
        let err = parse_line("no-equals").unwrap_err();
        assert_eq!(err, ParseError::MissingEquals("no-equals".to_string()));
        assert!(err.to_string().contains("no-equals"));
    }

    #[test]
    fn parse_config_ok_multiline() {
        // 正常路径：多行配置解析成表，空行被跳过
        let cfg = parse_config("host = 127.0.0.1\n\nport = 8080").unwrap();
        assert_eq!(cfg.get("host").map(String::as_str), Some("127.0.0.1"));
        assert_eq!(cfg.get("port").map(String::as_str), Some("8080"));
        assert_eq!(cfg.len(), 2);
    }

    #[test]
    fn parse_config_duplicate_key() {
        // 异常路径：重复 key 报 DuplicateKey（返回 Err，不 panic）
        let err = parse_config("a = 1\nb = 2\na = 3").unwrap_err();
        assert_eq!(err, ParseError::DuplicateKey("a".to_string()));
    }

    #[test]
    fn parse_config_via_result() -> Result<(), ParseError> {
        // Result 返回测试：Err 时 ? 传播，测试失败并打印错误（比 unwrap 信息更友好）
        let cfg = parse_config("host = 127.0.0.1\nport = 8080")?;
        assert_eq!(cfg.get("host").map(String::as_str), Some("127.0.0.1"));
        Ok(())
    }

    #[test]
    #[should_panic(expected = "config text must be valid")]
    fn checked_panics_on_bad_input() {
        // panic 契约：便捷入口对非法输入 panic，验证调用契约
        let _ = parse_config_checked("bad line");
    }
}
