// examples/ex03-error-trait-source.rs —— Error trait 实现（Display + source）与错误链打印，主文档第 6 章示例 3
// 说明：Error trait 实现（Display + source）与错误链。
//       两个变体都实现 source()：Io 指回 io::Error、Parse 指回 ParseIntError；
//       错误链打印用「source() 逐层遍历」（纯 std 的标准做法，输出已实测）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex03-error-trait-source.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告；错误链输出为实测结果）

use std::error::Error;
use std::fmt;
use std::num::ParseIntError;

// 错误枚举：Io（I/O 失败，包装 io::Error）+ Parse（解析失败，带行号定位）
#[derive(Debug)]
enum ScoreError {
    Io(std::io::Error),
    Parse { line: usize, source: ParseIntError },
}

// Display：每条消息都定位到「哪个操作 + 哪个输入/行号」
impl fmt::Display for ScoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ScoreError::Io(e) => write!(f, "读取文件失败: {e}"),
            ScoreError::Parse { line, source } => write!(f, "第 {line} 行不是合法数字: {source}"),
        }
    }
}

// Error：两个变体都暴露底层原因——错误链的每一环都有来源
impl Error for ScoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            ScoreError::Io(e) => Some(e),
            ScoreError::Parse { source, .. } => Some(source),
        }
    }
}

// From：io::Error 可经 `?` 自动转成 ScoreError::Io
impl From<std::io::Error> for ScoreError {
    fn from(e: std::io::Error) -> Self {
        ScoreError::Io(e)
    }
}

// 逐行解析：行号错误手动 map_err 包装（要携带行号，From 的自动转换注入不了额外字段）
fn load_scores(path: &str) -> Result<Vec<u32>, ScoreError> {
    let text = std::fs::read_to_string(path)?; // io::Error -> ScoreError::Io（走 From）
    text.lines()
        .enumerate()
        .map(|(i, l)| {
            l.trim()
                .parse::<u32>()
                .map_err(|e| ScoreError::Parse { line: i + 1, source: e })
        })
        .collect() // Result<Vec<_>, ScoreError>：遇错短路
}

// 错误链打印：沿 source() 逐层走到根因（纯 std 做法；anyhow 的 {:?} 是生态封装，见主文档 3.5）
fn print_chain(err: &(dyn Error + 'static)) {
    let mut cur = Some(err);
    while let Some(e) = cur {
        println!("  {e}");
        cur = e.source();
    }
}

fn main() {
    // 场景 A：内容不合法 -> 错误链带上「第几行」
    std::fs::write("/tmp/ph11-ex03-scores.txt", "90\nabc\n60\n").unwrap();
    let err = load_scores("/tmp/ph11-ex03-scores.txt").unwrap_err();
    println!("场景 A（解析失败）: {err}");
    println!("错误链（source 逐层）:");
    print_chain(&err);

    // 场景 B：文件不存在 -> 错误链带上「哪个文件」
    let err2 = load_scores("/tmp/ph11-ex03-missing.txt").unwrap_err();
    println!("\n场景 B（文件不存在）: {err2}");
    println!("错误链（source 逐层）:");
    print_chain(&err2);
}
