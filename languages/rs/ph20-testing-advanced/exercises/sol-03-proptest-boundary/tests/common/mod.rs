//! sol-03 共享策略：proptest 领域策略（值发生器 + 收缩器）。
//!
//! 策略设计要点：把失败的搜索空间聚焦到被测对象容易出错的区域。纯任意字节只能
//! 测「不 panic」；要测 roundtrip 语义必须生成**结构合法**的输入。这里把 record
//! 分成两个生成器再按权重混合：
//! - 常规 record：key/value 长度在宽区间内随机；
//! - 边界 record：value 长度钉在 0/1/64/65（字段边界正是长度解析 bug 高发区）。
//!
//! 权重偏向常规，边界保持足够出现率，proptest 失败收缩时两种都会被简化。
#![allow(dead_code)]

use proptest::prelude::*;

use record_parser::{Op, WalWriter};

/// 把 (seq, is_delete, key, value) 规范成合法 record 描述（Delete 强制空 value）。
fn normalize(
    seq: u64,
    is_delete: bool,
    key: Vec<u8>,
    value: Vec<u8>,
) -> (u64, Op, Vec<u8>, Vec<u8>) {
    if is_delete {
        (seq, Op::Delete, key, Vec::new())
    } else {
        (seq, Op::Put, key, value)
    }
}

/// 常规 record：key 1..=64B、value 0..=128B，内容任意。
pub fn random_record() -> impl Strategy<Value = (u64, Op, Vec<u8>, Vec<u8>)> {
    (
        any::<u64>(),
        prop::bool::ANY,
        prop::collection::vec(any::<u8>(), 1..=64),
        prop::collection::vec(any::<u8>(), 0..=128),
    )
        .prop_map(|(seq, is_delete, key, value)| normalize(seq, is_delete, key, value))
}

/// 边界 value 长度：0/1/64/65 各一份。
pub fn boundary_value_len() -> impl Strategy<Value = usize> {
    prop_oneof![Just(0usize), Just(1), Just(64), Just(65)]
}

/// 边界 record：value 长度钉在边界值上，其余与常规一致。
pub fn boundary_record() -> impl Strategy<Value = (u64, Op, Vec<u8>, Vec<u8>)> {
    (
        any::<u64>(),
        prop::bool::ANY,
        prop::collection::vec(any::<u8>(), 1..=64),
        boundary_value_len(),
    )
        .prop_flat_map(|(seq, is_delete, key, vlen)| {
            // 长度策略 → 具体 vec：flat_map 让「先抽长度、再按长度生成内容」成立
            prop::collection::vec(any::<u8>(), vlen)
                .prop_map(move |value| normalize(seq, is_delete, key.clone(), value))
        })
}

/// 混合：4 份边界 + 9 份常规。
pub fn record() -> impl Strategy<Value = (u64, Op, Vec<u8>, Vec<u8>)> {
    prop_oneof![4 => boundary_record(), 9 => random_record()]
}

/// 一段 0..=8 条合法 record 的日志描述。
pub fn log() -> impl Strategy<Value = Vec<(u64, Op, Vec<u8>, Vec<u8>)>> {
    prop::collection::vec(record(), 0..=8)
}

/// 任意字节（0..=1023）：轰炸「解析不 panic」类性质。
pub fn arbitrary_bytes() -> impl Strategy<Value = Vec<u8>> {
    prop::collection::vec(any::<u8>(), 0..1024)
}

/// 编码辅助：record 描述 → 日志字节（经被测对象自带的 WalWriter）。
pub fn encode(entries: &[(u64, Op, Vec<u8>, Vec<u8>)]) -> Vec<u8> {
    let mut w = WalWriter::new();
    for (seq, op, key, value) in entries {
        w.append(*seq, *op, key, value);
    }
    w.as_bytes().to_vec()
}
