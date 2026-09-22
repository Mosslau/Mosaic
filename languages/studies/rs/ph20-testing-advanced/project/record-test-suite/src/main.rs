//! record-test-suite 演示 CLI：把「测试套件的数据」跑给肉眼看。
//!
//! - 无参数：跑一段内存演示日志（Put/Delete/Put）并打印；
//! - `record-test-suite <file.wal>`：解析真实 WAL 文件并打印每条 record；
//! - `--matrix`：加载 tests/fixtures 错误样例矩阵并打印每类结果的判定，
//!   演示「异常样例测试」的判定逻辑（真正的断言在 tests/，这里只汇报）。
//!
//! 错误处理遵循 rust-patterns：应用层用显式 `Result` + 错误传播，不裸 unwrap；
//! 文件读取失败打印明确错误并以非 0 退出。

use std::env;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use record_test_suite::{records, Op, WalError, WalWriter};

fn dump(label: &str, bytes: &[u8]) -> Result<usize, WalError> {
    println!("== {label}（{} 字节）==", bytes.len());
    let mut count = 0usize;
    for item in records(bytes) {
        let rec = item?;
        count += 1;
        println!("  {count:>3}. {rec}");
    }
    println!("共 {count} 条 record\n");
    Ok(count)
}

fn matrix_report() -> Result<(), String> {
    let dir = fixtures_dir();
    let names = [
        "sample_put_delete_put.hex",
        "err_bad_magic.hex",
        "err_unknown_op.hex",
        "err_checksum_flip.hex",
        "err_klen_overflow.hex",
        "err_truncated_tail.hex",
        "boundary_empty.hex",
    ];
    println!("== 错误样例矩阵抽查（完整断言见 tests/anomaly_matrix.rs）==");
    for name in names {
        let text =
            std::fs::read_to_string(dir.join(name)).map_err(|e| format!("读 {name} 失败：{e}"))?;
        let bytes = decode_hex(&text).map_err(|e| format!("{name}：{e}"))?;
        let verdict = match records(&bytes).next() {
            None => "空日志（干净结束）".to_string(),
            Some(Ok(_)) => "有 record".to_string(),
            Some(Err(e)) => format!("Err：{e}"),
        };
        println!("  {name:<32} {verdict}");
    }
    Ok(())
}

fn fixtures_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures")
}

fn decode_hex(text: &str) -> Result<Vec<u8>, String> {
    let compact: String = text
        .lines()
        .filter(|l| !l.trim_start().starts_with('#'))
        .flat_map(str::chars)
        .filter(|c| !c.is_whitespace())
        .collect();
    if !compact.len().is_multiple_of(2) {
        return Err("hex 长度不是偶数".to_string());
    }
    (0..compact.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&compact[i..i + 2], 16)
                .map_err(|e| format!("非法 hex 段 {}：{e}", &compact[i..i + 2]))
        })
        .collect()
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().skip(1).collect();
    match args.as_slice() {
        [] => {
            let mut w = WalWriter::new();
            w.append(1, Op::Put, b"temperature", b"36.5");
            w.append(2, Op::Put, b"city", b"tokyo");
            w.append(3, Op::Delete, b"humidity", b"");
            dump("内存演示日志", w.as_bytes()).map_err(|e| e.to_string())?;
            matrix_report()?;
            Ok(())
        }
        [flag] if flag == "--matrix" => {
            matrix_report()?;
            Ok(())
        }
        [path] => {
            let bytes = std::fs::read(path).map_err(|e| format!("读取 {path} 失败：{e}"))?;
            dump(&format!("文件 {path}"), &bytes).map_err(|e| e.to_string())?;
            Ok(())
        }
        _ => Err("用法：record-test-suite [<file.wal> | --matrix]".to_string()),
    }
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}
