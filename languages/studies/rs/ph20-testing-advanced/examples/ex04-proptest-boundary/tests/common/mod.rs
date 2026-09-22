//! ex04 属性测试的共享策略与构造辅助。
//!
//! proptest 的策略（Strategy）是值发生器 + 收缩器（shrinker）的组合：
//! `prop::collection::vec(any::<u8>(), 0..64)` 表示「0..=63 个任意 u8」，
//! 失败时 proptest 会沿生成树自动收缩到最小反例。这里的策略都是**被测对象领域
//! 自定义策略**——从「字节的分布」升级到「结构合法的日志」：roundtrip 属性
//! 必须喂合法输入才有意义，而「解析不 panic」属性必须喂任意字节才可怕。
#![allow(dead_code)] // 各属性文件按需引用，未用到的辅助统一豁免

use proptest::prelude::*;

use ex04_proptest_boundary::{Op, WalWriter};

/// 任意字节（长度 0..=511）：喂给「解析永不 panic」类属性。
pub fn any_bytes() -> impl Strategy<Value = Vec<u8>> {
    prop::collection::vec(any::<u8>(), 0..512)
}

/// 合法 record 描述：(seq, op, key, value)。key 1..=64B、value 0..=64B，
/// 两个长度都压着「空」与「非空」边界；Delete 记录的 value 恒为空。
pub fn record() -> impl Strategy<Value = (u64, Op, Vec<u8>, Vec<u8>)> {
    (
        any::<u64>(),
        prop::bool::ANY,
        prop::collection::vec(any::<u8>(), 1..=64),
        prop::collection::vec(any::<u8>(), 0..=64),
    )
        .prop_map(|(seq, is_delete, key, value)| {
            if is_delete {
                (seq, Op::Delete, key, Vec::new()) // Delete 约定空 value
            } else {
                (seq, Op::Put, key, value)
            }
        })
}

/// 一段 0..=16 条合法 record 的日志描述。
pub fn log() -> impl Strategy<Value = Vec<(u64, Op, Vec<u8>, Vec<u8>)>> {
    prop::collection::vec(record(), 0..=16)
}

/// 把 record 描述编码成字节（构造辅助；编码器来自被测 crate 本身）。
pub fn encode(entries: &[(u64, Op, Vec<u8>, Vec<u8>)]) -> Vec<u8> {
    let mut w = WalWriter::new();
    for (seq, op, key, value) in entries {
        w.append(*seq, *op, key, value);
    }
    w.as_bytes().to_vec()
}

/// 「合法单条 record + 任意后缀」：验证解析器只消费自己的字段、绝不读穿边界。
/// 后缀可以是任意字节——包括恰好长得像下一条 record 前缀的字节。
pub fn record_with_suffix() -> impl Strategy<Value = (Vec<u8>, Vec<u8>)> {
    (record(), prop::collection::vec(any::<u8>(), 0..=128)).prop_map(
        |((seq, op, key, value), suffix)| {
            let mut w = WalWriter::new();
            w.append(seq, op, &key, &value);
            let mut bytes = w.as_bytes().to_vec();
            bytes.extend_from_slice(&suffix);
            (bytes, suffix)
        },
    )
}
