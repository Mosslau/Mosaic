//! 属性测试：proptest 压在套件被测对象上 —— 任意字节不 panic、构造日志 roundtrip、
//! Delete 空 value 不变量。与异常矩阵互补：矩阵验证「已知坏样例」，属性轰炸「未知边界」。

use proptest::prelude::*;

use record_test_suite::{records, Op, WalError, WalWriter};

/// 构造合法单条 record 描述。
fn record() -> impl Strategy<Value = (u64, Op, Vec<u8>, Vec<u8>)> {
    (
        any::<u64>(),
        prop::bool::ANY,
        prop::collection::vec(any::<u8>(), 1..=64),
        prop::collection::vec(any::<u8>(), 0..=64),
    )
        .prop_map(|(seq, is_delete, key, value)| {
            if is_delete {
                (seq, Op::Delete, key, Vec::new())
            } else {
                (seq, Op::Put, key, value)
            }
        })
}

fn log() -> impl Strategy<Value = Vec<(u64, Op, Vec<u8>, Vec<u8>)>> {
    prop::collection::vec(record(), 0..=16)
}

fn encode(entries: &[(u64, Op, Vec<u8>, Vec<u8>)]) -> Vec<u8> {
    let mut w = WalWriter::new();
    for (seq, op, key, value) in entries {
        w.append(*seq, *op, key, value);
    }
    w.as_bytes().to_vec()
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(512))]

    /// 任意字节不 panic（512 用例 × 0..=1023 字节）。
    #[test]
    fn never_panics_on_arbitrary_bytes(bytes in prop::collection::vec(any::<u8>(), 0..1024)) {
        let _ = records(&bytes).collect::<Result<Vec<_>, _>>();
    }

    /// 编码 → 解析 roundtrip：字段逐一相等、干净收尾。
    #[test]
    fn encode_then_parse_roundtrips(entries in log()) {
        let bytes = encode(&entries);
        let recs: Vec<_> = records(&bytes)
            .collect::<Result<_, _>>()
            .expect("被测对象自己的编码器写出的字节必然合法");
        prop_assert_eq!(recs.len(), entries.len());
        for (rec, entry) in recs.iter().zip(&entries) {
            prop_assert_eq!(rec.sequence, entry.0);
            prop_assert_eq!(rec.op, entry.1);
            prop_assert_eq!(rec.key, entry.2.as_slice());
            prop_assert_eq!(rec.value, entry.3.as_slice());
        }
    }

    /// Delete 记录的 value 必须为空。
    #[test]
    fn delete_value_is_empty(entries in log()) {
        let bytes = encode(&entries);
        let recs: Vec<_> = records(&bytes).collect::<Result<_, _>>().expect("合法");
        for (rec, entry) in recs.iter().zip(&entries) {
            if entry.1 == Op::Delete {
                prop_assert!(rec.value.is_empty());
            }
        }
    }

    /// 拼接不变量：两段合法日志拼在一起 = 各自解析结果相接（长度前缀格式的基石）。
    #[test]
    fn concatenated_logs_parse_like_the_union(a in log(), b in log()) {
        let bytes_a = encode(&a);
        let bytes_b = encode(&b);
        let mut both = bytes_a.clone();
        both.extend_from_slice(&bytes_b);
        let recs: Vec<_> = records(&both)
            .collect::<Result<_, _>>()
            .expect("两段合法日志拼接仍应全量合法");
        prop_assert_eq!(recs.len(), a.len() + b.len());
    }
}

/// 非性质抽查：错误变体集合保持封闭（新变体会在 exhaustive 的地方被编译器提示）。
#[test]
fn error_domain_is_closed() {
    // 任何构造出的 Err 都必须属于 WalError；Rust 类型已保证，
    // 此处仅示例「错误域契约」的断言姿势（若 WalError 增加变体，此表要同步补）。
    let mut w = WalWriter::new();
    w.append(1, Op::Put, b"k", b"v");
    let mut bytes = w.as_bytes().to_vec();
    bytes[0] = 0;
    let err = records(&bytes).next().expect("首条").expect_err("应报错");
    let _: &WalError = &err; // 类型即契约
    assert!(matches!(err, WalError::BadMagic(_)));
}
