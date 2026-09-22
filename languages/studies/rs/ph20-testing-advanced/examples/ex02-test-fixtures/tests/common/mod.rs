//! ex02 测试夹具的公共辅助（构造辅助 + 设备夹具 + 数据夹具读取）。
//!
//! fixtures 分两类（对应主文档 3.3）：
//! - **数据夹具**：tests/fixtures/*.hex —— 固定样例以文本文件形式入库，测试经
//!   [`decode_hex_fixture`] 解码后喂解析器；固定字节意味着可 diff、可跨机器复现；
//! - **构造辅助**：[`build_log`] 在内存里按参数生成任意日志，供需要大量/变长数据的用例；
//! - **设备夹具**：[`TempFile`] 把字节落到系统临时目录的真实文件，Drop 时自动清理——
//!   不需要「手工 remove_file」也能在断言失败/panic 时保证清理。
#![allow(dead_code)] // 每个 tests/*.rs 各自内联本文件，未必用到全部辅助 → 统一豁免

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

use ex02_test_fixtures::{Op, WalWriter};

/// 数据夹具目录的绝对路径：以 `CARGO_MANIFEST_DIR` 为锚，任何工作目录下都能跑。
pub fn fixtures_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures")
}

/// 读取并解码一个 `.hex` 数据夹具。
/// 格式：`#` 开头是注释行，其余是十六进制字节（可跨行，忽略空白）。
pub fn decode_hex_fixture(name: &str) -> Vec<u8> {
    let path = fixtures_dir().join(name);
    let text = fs::read_to_string(&path).unwrap_or_else(|e| panic!("读取夹具 {path:?} 失败：{e}"));
    let compact: String = text
        .lines()
        .filter(|l| !l.trim_start().starts_with('#'))
        .flat_map(str::chars)
        .filter(|c| !c.is_whitespace())
        .collect();
    assert!(
        compact.len().is_multiple_of(2),
        "夹具 {name} 含奇数个 hex 字符"
    );
    (0..compact.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&compact[i..i + 2], 16)
                .unwrap_or_else(|e| panic!("夹具 {name} hex 解析失败：{e}"))
        })
        .collect()
}

/// 构造辅助：把一组「记录描述」编码成一条 WAL 日志字节（等价于直接调 WalWriter）。
/// 用例可以用它与解析器做 roundtrip，不必手写魔数/CRC。
pub fn build_log(entries: &[(u64, Op, &[u8], &[u8])]) -> Vec<u8> {
    let mut w = WalWriter::new();
    for (seq, op, key, value) in entries {
        w.append(*seq, *op, key, value);
    }
    w.as_bytes().to_vec()
}

/// 三段合法日志的快捷数据夹具（与 tests/fixtures/sample_put_delete_put.hex 同内容）。
pub fn sample_log() -> Vec<u8> {
    build_log(&[
        (1, Op::Put, b"temperature", b"36.5"),
        (2, Op::Delete, b"humidity", b""),
        (3, Op::Put, b"city", b"tokyo"),
    ])
}

/// 设备夹具：把 `bytes` 写进系统临时目录的真实文件，`Drop` 时自动删除。
/// 并行测试用单调计数器保证文件名不撞车。
pub struct TempFile {
    path: PathBuf,
}

impl TempFile {
    pub fn new(tag: &str, bytes: &[u8]) -> Self {
        static SEQ: AtomicU64 = AtomicU64::new(0);
        let seq = SEQ.fetch_add(1, Ordering::Relaxed);
        let mut path = std::env::temp_dir();
        path.push(format!("ph20-ex02-{}-{seq}-{tag}.wal", std::process::id()));
        fs::write(&path, bytes).expect("写临时 WAL（测试夹具上下文）");
        TempFile { path }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path); // 清理失败不 panic（幂等即可）
    }
}
