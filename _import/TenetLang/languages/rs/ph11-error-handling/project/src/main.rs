// 来源：languages/rs/ph11-error-handling/project/ —— roadmap ph11 推荐项目「可靠 CLI」
// 说明：成绩报告生成器（score-report）——读取 "姓名,分数" 文本文件，逐行解析、校验、
//       聚合（总数/总和/平均/最高/最低）并输出报告；任何一步出错都给出「可定位」的
//       错误消息（哪个文件、哪一行、什么值、底层原因），退出码非 0。
//       本文件把 ph11 的错误处理知识点落成一体：自定义错误枚举（Display + Error +
//       From + source 错误链）、? 自动转换、错误链打印、契约性 panic（便捷入口），
//       以及正常/异常路径单元测试。零第三方依赖，单文件。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings src/main.rs -o /tmp/proj
// 运行：/tmp/proj <文件路径>（无参数或参数个数不对时打印用法，退出码 2）
// 测试：rustc --edition 2021 -D warnings --test src/main.rs -o /tmp/proj_test && /tmp/proj_test
// 验证状态：已验证（编译零警告；8 个单元测试全部通过）

use std::env;
use std::error::Error;
use std::fmt;
use std::num::ParseIntError;
use std::process::ExitCode;

// ===== 错误模型：闭集枚举，调用方可 match 穷尽；source() 暴露底层原因 =====

#[derive(Debug)]
enum ScoreError {
    Io(std::io::Error),                         // 文件读不了
    MissingComma { line: usize, text: String },  // 该行没有 ',' 分隔符
    BadScore { line: usize, value: String, source: ParseIntError }, // 分数不是数字
    OutOfRange { line: usize, value: i32 },     // 分数超出 0-100
}

impl fmt::Display for ScoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ScoreError::Io(e) => write!(f, "读取文件失败: {e}"),
            ScoreError::MissingComma { line, text } => {
                write!(f, "第 {line} 行缺少逗号分隔符: {text:?}")
            }
            ScoreError::BadScore { line, value, source } => {
                write!(f, "第 {line} 行分数 {value:?} 不是数字: {source}")
            }
            ScoreError::OutOfRange { line, value } => {
                write!(f, "第 {line} 行分数 {value} 超出 0-100")
            }
        }
    }
}

impl Error for ScoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            ScoreError::Io(e) => Some(e),
            ScoreError::BadScore { source, .. } => Some(source),
            ScoreError::MissingComma { .. } | ScoreError::OutOfRange { .. } => None,
        }
    }
}

// From：io::Error 可经 `?` 自动转成 ScoreError::Io
impl From<std::io::Error> for ScoreError {
    fn from(e: std::io::Error) -> Self {
        ScoreError::Io(e)
    }
}

// ===== 领域模型 =====

#[derive(Debug, PartialEq, Eq)]
struct Record {
    name: String,
    score: i32,
}

/// 解析一行 "姓名,分数"：缺逗号/非数字/越界分别报错，错误消息都带行号
fn parse_record(line: &str, line_no: usize) -> Result<Record, ScoreError> {
    let (name, score_str) = line
        .split_once(',')
        .ok_or_else(|| ScoreError::MissingComma { line: line_no, text: line.to_string() })?;
    let score: i32 = score_str
        .trim()
        .parse()
        .map_err(|source| ScoreError::BadScore {
            line: line_no,
            value: score_str.trim().to_string(),
            source,
        })?;
    if !(0..=100).contains(&score) {
        return Err(ScoreError::OutOfRange { line: line_no, value: score });
    }
    Ok(Record { name: name.trim().to_string(), score })
}

/// 文本级解析核心（与文件 I/O 解耦，便于单元测试直接喂文本）：空行合法，跳过
fn parse_text(text: &str) -> Result<Vec<Record>, ScoreError> {
    text.lines()
        .enumerate()
        .filter(|(_, l)| !l.trim().is_empty())
        .map(|(i, l)| parse_record(l, i + 1))
        .collect() // Result<Vec<_>, _>：遇错短路
}

/// 读文件 + 解析：io::Error 经 From 自动转成 ScoreError::Io
fn load_scores(path: &str) -> Result<Vec<Record>, ScoreError> {
    let text = std::fs::read_to_string(path)?;
    parse_text(&text)
}

// ===== 报告聚合 =====

#[derive(Debug, PartialEq, Eq)]
struct Report {
    total: usize,
    sum: i64,
    max: i32,
    min: i32,
}

fn build_report(records: &[Record]) -> Report {
    let total = records.len();
    let sum: i64 = records.iter().map(|r| r.score as i64).sum();
    let max = records.iter().map(|r| r.score).max().unwrap_or(0);
    let min = records.iter().map(|r| r.score).min().unwrap_or(0);
    Report { total, sum, max, min }
}

fn print_report(report: &Report) {
    let avg = if report.total == 0 { 0.0 } else { report.sum as f64 / report.total as f64 };
    println!("成绩报告（共 {} 条）", report.total);
    println!("总分: {}, 平均: {:.1}, 最高: {}, 最低: {}", report.sum, avg, report.max, report.min);
}

// ===== 入口 =====

fn run(path: &str) -> Result<(), ScoreError> {
    let records = load_scores(path)?;
    let report = build_report(&records);
    print_report(&report);
    Ok(())
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!("用法: score-report <文件路径>");
        eprintln!("文件每行格式: 姓名,分数（分数 0-100），空行忽略");
        return ExitCode::from(2); // 用法错误
    }
    match run(&args[1]) {
        Ok(()) => ExitCode::SUCCESS, // 0：成功
        Err(e) => {
            // 清晰错误提示：Display 一行 + 错误链逐层（source 遍历到根因）
            eprintln!("错误: {e}");
            let mut cur = e.source(); // 从底层原因开始遍历，避免重复顶层消息
            while let Some(err) = cur {
                eprintln!("  原因: {err}");
                cur = err.source();
            }
            ExitCode::from(1) // 1：数据/IO 错误
        }
    }
}

// ===== 单元测试：正常路径 + 异常路径 + 聚合 + 错误链 =====

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_record_ok() {
        // 正常路径：解析成功，首尾空格被 trim
        assert_eq!(
            parse_record("Alice, 90", 1).unwrap(),
            Record { name: "Alice".to_string(), score: 90 }
        );
    }

    #[test]
    fn parse_record_missing_comma() {
        // 异常路径：缺逗号 -> MissingComma，带行号与原文
        let err = parse_record("no-comma-here", 3).unwrap_err();
        assert!(matches!(err, ScoreError::MissingComma { line: 3, .. }));
        assert!(err.to_string().contains("第 3 行"));
    }

    #[test]
    fn parse_record_bad_score() {
        // 异常路径：分数不是数字 -> BadScore，source() 指回 ParseIntError（错误链）
        let err = parse_record("Bob,abc", 5).unwrap_err();
        match &err {
            ScoreError::BadScore { line: 5, value, .. } => assert_eq!(value, "abc"),
            _ => panic!("应是 BadScore"),
        }
        assert!(err.source().is_some()); // 错误链存在底层原因
    }

    #[test]
    fn parse_record_out_of_range() {
        // 异常路径：分数越界 -> OutOfRange
        let err = parse_record("Cara,150", 7).unwrap_err();
        assert!(matches!(err, ScoreError::OutOfRange { line: 7, value: 150 }));
    }

    #[test]
    fn parse_text_ok_skips_empty_lines() {
        // 正常路径：多行 + 空行跳过
        let records = parse_text("A,80\n\nB,90\n").unwrap();
        assert_eq!(records.len(), 2);
        assert_eq!(records[0].score, 80);
        assert_eq!(records[1].score, 90);
    }

    #[test]
    fn parse_text_error_carries_line_number() {
        // 异常路径：第 2 行出错 -> 错误携带正确的行号（短路在中间行）
        let err = parse_text("A,80\nbad-line\nC,90\n").unwrap_err();
        assert!(matches!(err, ScoreError::MissingComma { line: 2, .. }));
    }

    #[test]
    fn build_report_aggregates() {
        // 聚合：总数/总和/最高/最低
        let records = vec![
            Record { name: "A".into(), score: 75 },
            Record { name: "B".into(), score: 90 },
            Record { name: "C".into(), score: 80 },
        ];
        let report = build_report(&records);
        assert_eq!(report, Report { total: 3, sum: 245, max: 90, min: 75 });
    }

    #[test]
    fn io_error_chain_source() {
        // From 自动转换 + 错误链：不存在的文件 -> ScoreError::Io，source 指回 io::Error
        let err = load_scores("/tmp/ph11-proj-definitely-missing.txt").unwrap_err();
        assert!(matches!(err, ScoreError::Io(_)));
        assert!(err.source().is_some());
    }
}
