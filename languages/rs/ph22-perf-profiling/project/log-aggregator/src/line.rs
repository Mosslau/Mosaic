//! 日志行解析层：把一行文本日志拆成结构化字段（借用实现，零分配）。
//!
//! 目标格式（模拟一条「请求完成」日志，ph25 会把它换成真实的 WAL/SSTable
//! 场景，本阶段聚焦通用解析+聚合的优化方法论）：
//!
//! ```text
//! 2026-09-04T10:00:00.123Z INFO svc=auth op=login latency_ms=42
//! ```
//!
//! 字段空白分隔，前两段是时间与级别，之后是 `k=v`。解析只做空白切分与
//! `=` 定位，**全部字段借用输入行**——一个堆分配都不发生。

/// 一条已解析日志行的结构化视图（字段全部借用输入行）。
#[derive(Debug, PartialEq, Eq)]
pub struct LogLine<'a> {
    /// 服务名（svc=auth）。
    pub service: &'a str,
    /// 操作名（op=login）。
    pub op: &'a str,
    /// 请求延迟毫秒（latency_ms=42，缺失则为 None）。
    pub latency_ms: Option<u64>,
    /// 日志级别（INFO/WARN/ERROR），统计时也会用到。
    pub level: &'a str,
}

/// 解析失败：字段不全 / k=v 键不识别。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LineError {
    /// 缺少 svc=…（或值为空）。
    TooFewFields,
    /// latency_ms 不是数字。
    BadLatency,
}

/// 把行内一段 `k=v` 切片按 `=` 拆成 `(k, v)`（借用）。`=` 缺失时返回 None。
fn split_kv(token: &str) -> Option<(&str, &str)> {
    let idx = token.find('=')?;
    Some((&token[..idx], &token[idx + 1..]))
}

/// 解析一行日志（借用）。无法解析的脏行返回错误——由聚合层决定跳过。
pub fn parse_line(line: &str) -> Result<LogLine<'_>, LineError> {
    let mut service = None;
    let mut op = None;
    let mut latency_ms = None;
    let mut level = None;

    for (i, token) in line.split_whitespace().enumerate() {
        match i {
            0 => {} // 时间戳：本阶段不消费
            1 => level = Some(token),
            _ => {
                let Some((k, v)) = split_kv(token) else {
                    continue; // 非 k=v 的杂散 token 忽略
                };
                match k {
                    "svc" => service = Some(v),
                    "op" => op = Some(v),
                    "latency_ms" => {
                        latency_ms = Some(v.parse().map_err(|_| LineError::BadLatency)?)
                    }
                    _ => {}
                }
            }
        }
    }

    let service = service.ok_or(LineError::TooFewFields)?;
    if service.is_empty() {
        return Err(LineError::TooFewFields);
    }
    let level = level.unwrap_or("INFO");
    Ok(LogLine {
        service,
        op: op.unwrap_or(""),
        latency_ms,
        level,
    })
}

/// 构造 n 行结构可控的样例日志（service 集中在少数几个值上——真实日志的
/// 幂律分布：热点服务占大头）。返回拥有行。
pub fn sample_lines(n: usize) -> Vec<String> {
    const SVCS: [&str; 8] = [
        "auth", "auth", "auth", "kv", "kv", "search", "gateway", "billing",
    ];
    const OPS: [&str; 6] = ["login", "login", "read", "read", "write", "search"];
    (0..n)
        .map(|i| {
            let svc = SVCS[(i / 7) % SVCS.len()];
            let op = OPS[(i / 5) % OPS.len()];
            let latency = (i * 7919) % 240; // 0..240ms，可复现
            let level = match i % 10 {
                0..=7 => "INFO",
                8 => "WARN",
                _ => "ERROR",
            };
            format!("2026-09-04T10:00:00.{i:03}Z {level} svc={svc} op={op} latency_ms={latency}")
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_full_line() {
        let line = "2026-09-04T10:00:00.123Z INFO svc=auth op=login latency_ms=42";
        let l = parse_line(line).expect("合法行");
        assert_eq!(l.service, "auth");
        assert_eq!(l.op, "login");
        assert_eq!(l.latency_ms, Some(42));
        assert_eq!(l.level, "INFO");
    }

    #[test]
    fn missing_latency_is_none() {
        let line = "2026-09-04T10:00:00.123Z WARN svc=kv op=read";
        let l = parse_line(line).expect("合法行");
        assert_eq!(l.latency_ms, None);
        assert_eq!(l.level, "WARN");
    }

    #[test]
    fn error_cases() {
        assert_eq!(
            parse_line("just a few words").err(),
            Some(LineError::TooFewFields)
        );
        // svc= 后为空 → 视为缺服务
        assert_eq!(
            parse_line("2026-09-04T..Z INFO svc= op=x").err(),
            Some(LineError::TooFewFields)
        );
        assert!(matches!(
            parse_line("2026-09-04T..Z ERROR svc=kv latency_ms=abc"),
            Err(LineError::BadLatency)
        ));
    }

    #[test]
    fn sample_lines_parse_roundtrip() {
        let lines = sample_lines(50);
        assert_eq!(lines.len(), 50);
        for line in &lines {
            let l = parse_line(line).expect("样例行必须合法");
            assert!(!l.service.is_empty());
        }
    }
}
