//! 集成测试共享辅助模块（integration test shared module）。
//!
//! 惯例：**辅助模块不叫 `tests/common.rs`，而放 `tests/common/mod.rs`**——
//! `tests/` 下每个 `.rs`/`.rs` 文件都会被当成一个独立集成测试 crate 来编译运行，
//! 若直接放 `tests/common.rs`，它会被当测试目标、报「没有 #[test]」；
//! 放 `tests/common/mod.rs` 则只有显式 `mod common;` 引用它的测试文件才编译它，
//! 于是「每个集成测试文件开头 `mod common;`」就拿到了共享夹具。
//!
//! 本模块提供两类 fixture（对应主文档 3.3）：
//! - **数据夹具**：[`sample_log_bytes`] 构造一条确定性的三段合法日志；
//! - **设备夹具**：[`write_temp_wal`] 把字节落到系统临时目录的真实文件（用后即删）。
#![allow(dead_code)] // 每个 tests/*.rs 各自内联本文件，未必用到全部辅助 → 统一豁免

use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

// 依赖被测 crate 的 pub API（集成测试看不到内部实现，只能走公开接口）。
use ex01_unit_integration_tree::{Op, WalWriter};

/// 数据夹具：三段合法日志（Put/Delete/Put），字节固定，任何测试可对比。
pub fn sample_log_bytes() -> Vec<u8> {
    let mut w = WalWriter::new();
    w.append(1, Op::Put, b"temperature", b"36.5");
    w.append(2, Op::Delete, b"humidity", b"");
    w.append(3, Op::Put, b"city", b"tokyo");
    w.as_bytes().to_vec()
}

/// 设备夹具：把 `bytes` 写成独占路径的临时 WAL 文件，返回路径。
/// 计数器保证并行测试之间不撞名；测试结束由调用方 `remove_file`。
pub fn write_temp_wal(tag: &str, bytes: &[u8]) -> PathBuf {
    static SEQ: AtomicU64 = AtomicU64::new(0);
    let seq = SEQ.fetch_add(1, Ordering::Relaxed);
    let mut path = std::env::temp_dir();
    path.push(format!("ph20-ex01-{}-{seq}-{tag}.wal", std::process::id()));
    std::fs::write(&path, bytes).expect("写临时 WAL（测试夹具上下文，expect 即断言）");
    path
}
