// examples/log-analyzer/src/parser.rs —— 解析层：文本行 -> Record（只依赖 model）
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 1
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/log-analyzer/ 目录内执行）
// 运行：cargo run
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use crate::model::Record;

pub fn parse_line(line: &str) -> Option<Record> {
    let mut parts = line.splitn(3, ' ');
    let ts = parts.next()?.parse().ok()?;   // ? 传播 None（ph04/ph05）
    let level = parts.next()?.to_string();
    let message = parts.next()?.to_string();
    Some(Record { ts, level, message })
}

pub fn parse_all(input: &str) -> Vec<Record> {
    input.lines().filter_map(parse_line).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_valid_line() {
        let r = parse_line("1700000000 INFO boot ok").expect("应解析成功");
        assert_eq!(r.ts, 1_700_000_000);
        assert_eq!(r.level, "INFO");
        assert_eq!(r.message, "boot ok");
    }

    #[test]
    fn parse_bad_line_returns_none() {
        // 缺列 / 时间戳不是数字 / 完全空行都应失败
        assert_eq!(parse_line("1700000000 INFO"), None);
        assert_eq!(parse_line("abc WARN x"), None);
        assert_eq!(parse_line(""), None);
    }

    #[test]
    fn parse_all_skips_bad_lines() {
        let records = parse_all("1700000000 INFO boot ok\nbad line\n1700000002 ERROR disk full");
        assert_eq!(records.len(), 2);
    }
}
