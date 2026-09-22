//! record-test-suite 集成测试的共享辅助：fixtures 目录/解码、日志构造、假引擎模型。
#![allow(dead_code)]

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

use record_test_suite::{Op, WalWriter};

/// fixtures 目录：锚定 CARGO_MANIFEST_DIR，任何工作目录可跑。
pub fn fixtures_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures")
}

/// 解码 .hex 数据夹具（`#` 注释行 + 十六进制，可跨行）。
pub fn decode_hex_fixture(name: &str) -> Vec<u8> {
    let path = fixtures_dir().join(name);
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("读夹具 {path:?}：{e}"));
    let compact: String = text
        .lines()
        .filter(|l| !l.trim_start().starts_with('#'))
        .flat_map(str::chars)
        .filter(|c| !c.is_whitespace())
        .collect();
    assert!(compact.len().is_multiple_of(2), "夹具 {name} hex 长度奇数");
    (0..compact.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&compact[i..i + 2], 16)
                .unwrap_or_else(|e| panic!("夹具 {name} 非法 hex：{e}"))
        })
        .collect()
}

/// 日志构造辅助。
pub fn build_log(entries: &[(u64, Op, &[u8], &[u8])]) -> Vec<u8> {
    let mut w = WalWriter::new();
    for (seq, op, key, value) in entries {
        w.append(*seq, *op, key, value);
    }
    w.as_bytes().to_vec()
}

/// 设备夹具：写临时文件，Drop 自清理。
pub struct TempFile {
    path: PathBuf,
}

impl TempFile {
    pub fn new(tag: &str, bytes: &[u8]) -> Self {
        static SEQ: AtomicU64 = AtomicU64::new(0);
        let seq = SEQ.fetch_add(1, Ordering::Relaxed);
        let mut path = std::env::temp_dir();
        path.push(format!("ph20-suite-{}-{seq}-{tag}.wal", std::process::id()));
        std::fs::write(&path, bytes).expect("写临时 WAL（测试夹具上下文）");
        TempFile { path }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.path);
    }
}

/// 一条已应用操作（假引擎模型日志项）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Applied {
    pub seq: u64,
    pub op: Op,
    pub key: Vec<u8>,
    pub value: Vec<u8>,
}

/// 假引擎：解析出的 record 落地成语义（Put 覆盖写、Delete 删除），保留操作日志。
#[derive(Debug, Default)]
pub struct Engine {
    applied: Vec<Applied>,
    table: Vec<(Vec<u8>, Vec<u8>)>,
}

impl Engine {
    pub fn new() -> Self {
        Engine::default()
    }

    pub fn apply_bytes(&mut self, bytes: &[u8]) -> Result<usize, record_test_suite::WalError> {
        let mut count = 0;
        for item in record_test_suite::records(bytes) {
            let rec = item?;
            self.applied.push(Applied {
                seq: rec.sequence,
                op: rec.op,
                key: rec.key.to_vec(),
                value: rec.value.to_vec(),
            });
            match rec.op {
                Op::Put => {
                    if let Some(slot) = self.table.iter_mut().find(|(k, _)| k == rec.key) {
                        slot.1 = rec.value.to_vec();
                    } else {
                        self.table.push((rec.key.to_vec(), rec.value.to_vec()));
                    }
                }
                Op::Delete => self.table.retain(|(k, _)| k != rec.key),
            }
            count += 1;
        }
        Ok(count)
    }

    pub fn get(&self, key: &[u8]) -> Option<&[u8]> {
        self.table
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v.as_slice())
    }

    pub fn applied(&self) -> &[Applied] {
        &self.applied
    }

    pub fn len(&self) -> usize {
        self.table.len()
    }

    pub fn is_empty(&self) -> bool {
        self.table.is_empty()
    }
}
