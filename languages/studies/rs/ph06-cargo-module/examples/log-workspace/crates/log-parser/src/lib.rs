// examples/log-workspace/crates/log-parser/src/lib.rs —— 库：解析日志行
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 5
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build --workspace（在 examples/log-workspace/ 目录内执行）
// 测试：cargo test -p log-parser
// 验证状态：已验证（rustc 1.92.0）

#[derive(Debug, Clone, PartialEq)]
pub struct LogLine {
    pub ts: u64,
    pub level: String,
    pub message: String,
}

pub fn parse(line: &str) -> Option<LogLine> {
    let mut parts = line.splitn(3, ' ');
    let ts = parts.next()?.parse().ok()?;
    let level = parts.next()?.to_string();
    let message = parts.next()?.to_string();
    Some(LogLine { ts, level, message })
}

pub fn parse_all(input: &str) -> Vec<LogLine> {
    input.lines().filter_map(parse).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_valid() {
        let l = parse("1700000000 INFO boot ok").unwrap();
        assert_eq!(l.level, "INFO");
    }

    #[test]
    fn parse_invalid_returns_none() {
        assert_eq!(parse("oops"), None);
        // 一行合法 + 一行非法：只解析出 1 条
        assert_eq!(parse_all("1700000000 INFO ok\nbad").len(), 1);
    }
}
