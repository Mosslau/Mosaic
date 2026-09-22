// exercises/sol-01-split-project/src/parser.rs —— 练习 1 参考实现：解析层
// 拆分自 exercises/ex01-single-source.rs 的 parse_line / parse_all
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 sol-01-split-project/ 目录内执行）
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use crate::model::CityTemp;

pub fn parse_line(line: &str) -> Option<CityTemp> {
    let mut parts = line.split('\t');
    let ts = parts.next()?.parse().ok()?;
    let city = parts.next()?.to_string();
    let temp = parts.next()?.parse().ok()?;
    Some(CityTemp { ts, city, temp })
}

pub fn parse_all(input: &str) -> Vec<CityTemp> {
    input.lines().filter_map(parse_line).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_valid_line() {
        let r = parse_line("1700000000\tbeijing\t25.5").unwrap();
        assert_eq!(r.ts, 1_700_000_000);
        assert_eq!(r.city, "beijing");
        assert_eq!(r.temp, 25.5);
    }

    #[test]
    fn parse_bad_lines_return_none() {
        assert_eq!(parse_line("no-tabs"), None);
        assert_eq!(parse_line("1700000000\tbeijing"), None); // 缺温度列
        assert_eq!(parse_line("abc\tbeijing\t25.5"), None);   // 时间戳非法
    }

    #[test]
    fn parse_all_skips_bad_lines() {
        let records = parse_all("1700000000\tbeijing\t25.5\nbad\n1700000100\tshanghai\t28.0");
        assert_eq!(records.len(), 2);
    }
}
