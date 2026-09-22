//! sol-02 共享测试模块：构造辅助 + 设备夹具 + **假引擎（fake）**。
//!
//! 假引擎是一个只依赖被测解析器 pub API 的迷你模型：Put 写入、Delete 删除、
//! 同时保留一份「操作日志」供顺序断言。它是测试里的真实现替身——
//! 让集成测试聚焦「字节 → 语义」的契约，而不是真的去碰 KV 存储（ph25 的内容）。
#![allow(dead_code)]

use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

use record_parser::{Op, WalWriter};

/// 一条已应用的操作（假引擎的操作日志项）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Applied {
    pub seq: u64,
    pub op: Op,
    pub key: Vec<u8>,
    pub value: Vec<u8>,
}

/// 假引擎：解析出的 record 直接落地成语义（Put/Delete），可断言最终态与顺序。
#[derive(Debug, Default)]
pub struct Engine {
    applied: Vec<Applied>,
    table: Vec<(Vec<u8>, Vec<u8>)>, // 模拟 key→value 表（保持插入序，够教学用）
}

impl Engine {
    pub fn new() -> Self {
        Engine::default()
    }

    /// 解析一段日志并逐条应用到引擎；解析失败即停（不 panic，错误返回）。
    pub fn apply_bytes(&mut self, bytes: &[u8]) -> Result<usize, record_parser::WalError> {
        let mut count = 0;
        for item in record_parser::records(bytes) {
            let rec = item?;
            self.apply_one(&rec);
            count += 1;
        }
        Ok(count)
    }

    fn apply_one(&mut self, rec: &record_parser::Record<'_>) {
        self.applied.push(Applied {
            seq: rec.sequence,
            op: rec.op,
            key: rec.key.to_vec(),
            value: rec.value.to_vec(),
        });
        match rec.op {
            Op::Put => {
                if let Some(slot) = self.table.iter_mut().find(|(k, _)| k == rec.key) {
                    slot.1 = rec.value.to_vec(); // 覆盖写
                } else {
                    self.table.push((rec.key.to_vec(), rec.value.to_vec()));
                }
            }
            Op::Delete => self.table.retain(|(k, _)| k != rec.key),
        }
    }

    /// 查询：最终态里 key 的值（None = 不存在或已被删除）。
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

/// 构造辅助：把一组 record 描述编码成日志字节。
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
        path.push(format!("ph20-sol02-{}-{seq}-{tag}.wal", std::process::id()));
        std::fs::write(&path, bytes).expect("写临时 WAL（测试夹具上下文）");
        TempFile { path }
    }

    pub fn path(&self) -> &std::path::Path {
        &self.path
    }
}

impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.path);
    }
}
