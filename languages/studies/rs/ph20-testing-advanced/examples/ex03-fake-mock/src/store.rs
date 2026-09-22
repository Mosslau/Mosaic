//! Store 边界：被测对象 `replay_to` 依赖的抽象，以及一个可复用的 fake 实现。
//!
//! 设计意图：**把「解析」与「落库」之间立一道 trait 边界**。解析层（`record`）
//! 只产出一条条 record；要不要应用、应用到什么，由调用方注入。这道边界让
//! 测试可以注入 fake（行为）或 mock（交互/失败注入），也让 ph25 的真实引擎
//! 只需实现同一个 trait 就能接进来——接口边界是测试性的先决条件（主文档 3.7）。

use std::error::Error;
use std::fmt;

use crate::{records, Op, WalError};

/// 存储边界错误：trait 里「可失败」的返回点，正是 mock 要注入失败的地方。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoreError(pub String);

impl fmt::Display for StoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "存储错误：{}", self.0)
    }
}

impl Error for StoreError {}

/// 应用型存储的抽象：replay 时逐条把 record 应用进去。
pub trait Store {
    /// 把一条 record 应用到存储。返回 Err 表示本次应用失败，replay 应停止。
    fn apply(&mut self, op: Op, seq: u64, key: &[u8], value: &[u8]) -> Result<(), StoreError>;
}

/// 一次已成功应用的 record（fake 与 mock 都能用同一结构描述「发生过什么」）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub op: Op,
    pub seq: u64,
    pub key: Vec<u8>,
    pub value: Vec<u8>,
}

/// fake：MemoryStore 完整实现了 `Store` 的语义（追加到内存表）。
/// 它既是生产可用的「迷你引擎」（ph25 MemTable 的原型），又是测试里
/// 「行为正确性」最快的裁判——fake 是真实实现，不是造假。
#[derive(Debug, Default)]
pub struct MemoryStore {
    entries: Vec<Entry>,
}

impl MemoryStore {
    pub fn new() -> Self {
        MemoryStore::default()
    }

    /// 查看已应用的记录（供测试断言「发生了这些」）。
    pub fn entries(&self) -> &[Entry] {
        &self.entries
    }
}

impl Store for MemoryStore {
    fn apply(&mut self, op: Op, seq: u64, key: &[u8], value: &[u8]) -> Result<(), StoreError> {
        self.entries.push(Entry {
            op,
            seq,
            key: key.to_vec(),
            value: value.to_vec(),
        });
        Ok(())
    }
}

/// replay_to 的错误：解析失败或存储应用失败，带尽可能多的现场。
#[derive(Debug)]
pub enum ReplayError {
    /// 日志在第 seq 条附近解析失败（WAL 语义：损坏点之后不可信）。
    Parse(WalError),
    /// 解析成功但应用失败（存储故障，如磁盘满——mock 注入这类错误以测停止语义）。
    Apply {
        seq: u64,
        op: Op,
        source: StoreError,
    },
}

impl fmt::Display for ReplayError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ReplayError::Parse(e) => write!(f, "replay 解析失败：{e}"),
            ReplayError::Apply { seq, op, source } => {
                write!(f, "replay 应用 seq={seq}（{op:?}）失败：{source}")
            }
        }
    }
}

impl Error for ReplayError {}

/// 被测对象：把整段日志逐条解析并应用到一个 `Store`。
/// 只依赖 `Store` trait——fake 与 mock 在此汇合。
pub fn replay_to<S: Store>(store: &mut S, log: &[u8]) -> Result<usize, ReplayError> {
    let mut applied = 0;
    for item in records(log) {
        let rec = item.map_err(ReplayError::Parse)?;
        store
            .apply(rec.op, rec.sequence, rec.key, rec.value)
            .map_err(|source| ReplayError::Apply {
                seq: rec.sequence,
                op: rec.op,
                source,
            })?;
        applied += 1;
    }
    Ok(applied)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_log_applies_nothing() {
        let mut store = MemoryStore::new();
        assert_eq!(replay_to(&mut store, b"").expect("空日志"), 0);
        assert!(store.entries().is_empty());
    }

    #[test]
    fn memory_store_append_is_idempotent_free_by_design() {
        // fake 语义说明：replay 两次 = 应用两次（MemoryStore 没有去重）。
        // 这在 WAL 恢复里意味着：恢复必须从某个干净起点开始，否则重复应用——
        // ph25 会用 sequence 幂等性处理，本示例只把语义如实暴露给测试。
        let mut w = crate::WalWriter::new();
        w.append(1, crate::Op::Put, b"k", b"v");
        let mut store = MemoryStore::new();
        replay_to(&mut store, w.as_bytes()).expect("第一次");
        replay_to(&mut store, w.as_bytes()).expect("第二次");
        assert_eq!(store.entries().len(), 2);
    }
}
