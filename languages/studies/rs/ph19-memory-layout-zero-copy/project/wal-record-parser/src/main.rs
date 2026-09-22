//! WAL record 解析演示 CLI：
//!
//! - 无参数：构造一段内存日志（Put × 2 + Delete × 1）并逐条解析打印；
//! - `wal-record-parser <文件路径>`：把整文件读入内存并逐条解析打印。
//!
//! 读取用 `std::fs::read` 整读后由库做零拷贝解析；文件损坏时打印明确错误并以非 0 退出。
//! 用法示例见 project/README.md。运行/测试命令见文件头与 Cargo.toml 注释。

use std::env;
use std::process::ExitCode;
use wal_record_parser::{records, Op, WalWriter};

fn dump(label: &str, bytes: &[u8]) -> Result<usize, wal_record_parser::WalError> {
    println!("== {label}（{} 字节）==", bytes.len());
    let mut count = 0usize;
    for item in records(bytes) {
        let rec = item?;
        count += 1;
        println!("  {count:>3}. {rec}");
    }
    println!("共 {count} 条 record");
    Ok(count)
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    match args.as_slice() {
        [] => {
            // 内存演示日志
            let mut w = WalWriter::new();
            w.append(1, Op::Put, b"temperature", b"36.5");
            w.append(2, Op::Put, b"city", b"tokyo");
            w.append(3, Op::Delete, b"humidity", b"");
            if let Err(e) = dump("内存日志", w.as_bytes()) {
                eprintln!("解析失败：{e}");
                return ExitCode::FAILURE;
            }
            ExitCode::SUCCESS
        }
        [path] => match std::fs::read(path) {
            Ok(bytes) => match dump(&format!("文件 {path}"), &bytes) {
                Ok(_) => ExitCode::SUCCESS,
                Err(e) => {
                    eprintln!("解析失败：{e}");
                    ExitCode::FAILURE
                }
            },
            Err(e) => {
                eprintln!("读取 {path} 失败：{e}");
                ExitCode::FAILURE
            }
        },
        _ => {
            eprintln!("用法：wal-record-parser [<WAL 文件路径>]");
            ExitCode::FAILURE
        }
    }
}
