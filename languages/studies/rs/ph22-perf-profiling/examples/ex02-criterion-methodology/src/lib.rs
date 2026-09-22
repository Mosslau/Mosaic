//! ex02：criterion 方法论示例的被测对象（DUT）。
//!
//! 场景沿用 ph19/ph20 的「日志/协议解析」域：一条文本日志行
//! `"时间 级别 服务 操作 字段…"` 要拆成结构化字段。两条解析路径：
//!
//! - `parse_borrowed`：**借用路径** —— 字段直接借用输入行的切片（零拷贝）；
//! - `parse_owned`：**复制路径** —— 字段各 `to_string()` 成拥有数据
//!   （模拟把结果存进结构体跨函数返回、或写入聚合表的真实需求）。
//!
//! 基准的意义不在「谁更快」这种常识，而在**量化使用姿势的代价**：
//! owned 路径每行多几次堆分配，随行数放大后差别多大？这正是 criterion
//! 要给出数字的「先测量」环节。

/// 一行日志的结构化视图（借用版）。字段借用自输入行。
#[derive(Debug, PartialEq, Eq)]
pub struct ParsedLine<'a> {
    pub timestamp: &'a str,
    pub level: &'a str,
    pub service: &'a str,
    pub op: &'a str,
}

/// 一行日志的结构化视图（拥有版）。字段是独立分配的 String。
#[derive(Debug, PartialEq, Eq)]
pub struct OwnedLine {
    pub timestamp: String,
    pub level: String,
    pub service: String,
    pub op: String,
}

/// 行格式错误：字段数不足（最少 4 个）。
#[derive(Debug, PartialEq, Eq)]
pub struct LineTooShort;

/// 借用路径：把 `"ts level service op …"` 的前 4 个空白分隔字段借出来。
pub fn parse_borrowed(line: &str) -> Result<ParsedLine<'_>, LineTooShort> {
    let mut it = line.split_whitespace();
    let (Some(timestamp), Some(level), Some(service), Some(op)) =
        (it.next(), it.next(), it.next(), it.next())
    else {
        return Err(LineTooShort);
    };
    Ok(ParsedLine {
        timestamp,
        level,
        service,
        op,
    })
}

/// 复制路径：字段各拷成 String（4 次堆分配/行）。
pub fn parse_owned(line: &str) -> Result<OwnedLine, LineTooShort> {
    let borrowed = parse_borrowed(line)?;
    Ok(OwnedLine {
        timestamp: borrowed.timestamp.to_owned(),
        level: borrowed.level.to_owned(),
        service: borrowed.service.to_owned(),
        op: borrowed.op.to_owned(),
    })
}

/// 构造 `n` 行长度可控的样例日志，返回拥有行的 Vec（基准输入）。
pub fn sample_lines(n: usize) -> Vec<String> {
    (0..n)
        .map(|i| {
            format!(
                "2026-09-04T10:{:02}:{:02}.123Z INFO svc-{:<4} op-{:<4} seq={i}",
                (i / 60) % 60,
                i % 60,
                i % 37,
                i % 41
            )
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn borrowed_fields_match_owned() {
        let line = "2026-09-04T10:00:00.123Z INFO auth login seq=7";
        let b = parse_borrowed(line).expect("合法行");
        assert_eq!(b.timestamp, "2026-09-04T10:00:00.123Z");
        assert_eq!(b.level, "INFO");
        assert_eq!(b.service, "auth");
        assert_eq!(b.op, "login");
        // 零拷贝断言：借用切片的指针落在输入行内存内部
        let base = line.as_ptr() as usize;
        assert_eq!(b.service.as_ptr() as usize - base, 24 + 6); // 跳过 ts+1+level+1
    }

    #[test]
    fn owned_fields_copy_out() {
        let line = "2026-09-04T10:00:00.123Z WARN cache evict seq=1";
        let o = parse_owned(line).expect("合法行");
        assert_eq!(o.service, "cache");
        assert_eq!(o.op, "evict");
    }

    #[test]
    fn too_short_line_is_err() {
        assert_eq!(parse_borrowed("only two words").err(), Some(LineTooShort));
        assert_eq!(parse_owned("one").err(), Some(LineTooShort));
    }

    #[test]
    fn sample_lines_have_expected_shape() {
        let lines = sample_lines(3);
        assert_eq!(lines.len(), 3);
        for l in &lines {
            let p = parse_borrowed(l).expect("样例行应合法");
            assert_eq!(p.level, "INFO");
        }
    }
}
