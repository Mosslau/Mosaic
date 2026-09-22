// project/log-analyzer/crates/log-parser/src/lib.rs —— 解析层：日志行 -> LogLine（只依赖标准库）
// 来源：languages/rs/ph06-cargo-module/project/log-analyzer（阶段项目源码）
// 日志行格式：ts\tlevel\tsource\tmessage（制表符分隔），level 用 enum 表达（衔接 ph05）
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build --workspace（在 project/log-analyzer/ 目录内执行）
// 测试：cargo test -p log-parser
// 验证状态：已验证（rustc 1.92.0）

/// 日志级别：enum 替代魔法字符串（ph05 模式匹配的延续）
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Level {
    Debug,
    Info,
    Warn,
    Error,
}

impl std::str::FromStr for Level {
    type Err = String;

    fn from_str(s: &str) -> Result<Level, Self::Err> {
        match s {
            "DEBUG" => Ok(Level::Debug),
            "INFO" => Ok(Level::Info),
            "WARN" => Ok(Level::Warn),
            "ERROR" => Ok(Level::Error),
            other => Err(format!("未知日志级别: '{}'", other)),
        }
    }
}

impl std::fmt::Display for Level {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            Level::Debug => "DEBUG",
            Level::Info => "INFO",
            Level::Warn => "WARN",
            Level::Error => "ERROR",
        };
        write!(f, "{}", s)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct LogLine {
    pub ts: u64,         // 时间戳（Unix 秒）
    pub level: Level,    // 级别
    pub source: String,  // 来源（api-server / worker-1 / db-layer ...）
    pub message: String, // 消息内容
}

/// 解析单行日志：格式非法（缺列 / 时间戳非数字 / 级别未知 / 来源为空）返回 None
pub fn parse(line: &str) -> Option<LogLine> {
    let mut parts = line.splitn(4, '\t');
    let ts = parts.next()?.parse().ok()?;
    let level: Level = parts.next()?.parse().ok()?; // 经 FromStr 解析
    let source = parts.next()?.to_string();
    let message = parts.next()?.to_string();
    if source.is_empty() {
        return None;
    }
    Some(LogLine {
        ts,
        level,
        source,
        message,
    })
}

/// 解析多行：坏行自动跳过（filter_map 组合，ph04/ph05 基础）
pub fn parse_all(input: &str) -> Vec<LogLine> {
    input.lines().filter_map(parse).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_line() -> &'static str {
        "1700000000\tINFO\tapi-server\trequest handled: GET /health 200"
    }

    #[test]
    fn parse_valid_line() {
        let l = parse(valid_line()).unwrap();
        assert_eq!(l.ts, 1_700_000_000);
        assert_eq!(l.level, Level::Info);
        assert_eq!(l.source, "api-server");
        assert_eq!(l.message, "request handled: GET /health 200");
    }

    #[test]
    fn parse_all_four_levels() {
        for (s, expected) in [
            ("DEBUG", Level::Debug),
            ("INFO", Level::Info),
            ("WARN", Level::Warn),
            ("ERROR", Level::Error),
        ] {
            let line = format!("1\t{}\tsrc\tmsg", s);
            assert_eq!(parse(&line).unwrap().level, expected);
        }
    }

    #[test]
    fn parse_bad_lines_return_none() {
        assert_eq!(parse("no-tabs"), None); // 缺列
        assert_eq!(parse("abc\tINFO\tsrc\tmsg"), None); // 时间戳非法
        assert_eq!(parse("1\tFOO\tsrc\tmsg"), None); // 级别未知
        assert_eq!(parse("1\tINFO\t\tmsg"), None); // 来源为空
        assert_eq!(parse(""), None);
    }

    #[test]
    fn parse_all_skips_bad_lines() {
        let input = format!(
            "{}\nbad line\n{}",
            valid_line(),
            "1700000001\tERROR\tdb-layer\ttimeout"
        );
        assert_eq!(parse_all(&input).len(), 2);
    }

    #[test]
    fn level_roundtrip() {
        assert_eq!("WARN".parse::<Level>(), Ok(Level::Warn));
        assert_eq!(format!("{}", Level::Error), "ERROR");
        assert!("NOPE".parse::<Level>().is_err());
    }
}
