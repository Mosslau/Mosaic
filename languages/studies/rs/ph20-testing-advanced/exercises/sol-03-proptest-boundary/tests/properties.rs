//! sol-03 参考实现：proptest 性质 —— 任意字节不 panic、roundtrip 相等、
//! 长度越界报 TooLarge、编码字节解析出的字段逐一相等。
//! 收缩（shrinking）提示：任一性质失败，proptest 会打印 minimal failing input，
//! 并在 tests/*.proptest-regressions 文件里留一行可复现的回归用例。

mod common;

use proptest::prelude::*;

use record_parser::{parse_record, records, Op, WalError};

proptest! {
    #![proptest_config(ProptestConfig::with_cases(256))]

    /// 性质 1：任意字节进解析器，绝不 panic（panic 即失败并被收缩）。
    #[test]
    fn never_panics_on_arbitrary_bytes(bytes in common::arbitrary_bytes()) {
        let _ = records(&bytes).collect::<Result<Vec<_>, _>>();
        let _ = parse_record(&bytes);
    }

    /// 性质 2：roundtrip —— 编码器写出的日志必然逐条解析回来，字段全等。
    #[test]
    fn encode_then_parse_roundtrips(entries in common::log()) {
        let bytes = common::encode(&entries);
        let recs: Vec<_> = records(&bytes).collect::<Result<_, _>>()
            .expect("被测对象自己的编码器写出的字节必然合法");
        prop_assert_eq!(recs.len(), entries.len(), "条数不一致");
        for (rec, entry) in recs.iter().zip(&entries) {
            prop_assert_eq!(rec.sequence, entry.0);
            prop_assert_eq!(rec.op, entry.1);
            prop_assert_eq!(rec.key, entry.2.as_slice());
            prop_assert_eq!(rec.value, entry.3.as_slice());
        }
    }

    /// 性质 3：Delete 语义 —— 凡是 op=Delete 的 record，解析出的 value 必为空。
    #[test]
    fn delete_records_always_have_empty_value(entries in common::log()) {
        let bytes = common::encode(&entries);
        let recs: Vec<_> = records(&bytes).collect::<Result<_, _>>().expect("合法");
        for (rec, entry) in recs.iter().zip(&entries) {
            if entry.1 == Op::Delete {
                prop_assert!(rec.value.is_empty(), "Delete 的 value 必须为空");
            }
        }
    }
}

/// 非性质补充：klen 越过上限的字节必须报 TooLarge（DoS 闸门）。
/// 用手工构造的 25 字节头部即可触发——解析顺序是「先查长度上限、后切区间」。
#[test]
fn klen_over_max_reports_too_large() {
    use record_parser::{HEADER_LEN, MAGIC, MAX_KEY};
    let mut head = vec![0u8; HEADER_LEN];
    head[0..4].copy_from_slice(&MAGIC.to_le_bytes());
    head[16] = 1; // op = Put（解析顺序：魔数 → CRC → seq → op → klen 闸门）
    let klen = (MAX_KEY + 1) as u32;
    head[17..21].copy_from_slice(&klen.to_le_bytes()); // klen = MAX_KEY + 1
    assert!(matches!(
        parse_record(&head),
        Err(WalError::TooLarge { what: "key", .. })
    ));
}

/// 非性质补充：恰好等于上限的 klen 不触发 TooLarge 闸门（仍会因缺字节报 Truncated）。
#[test]
fn klen_equal_to_max_passes_gate_then_truncates() {
    use record_parser::{HEADER_LEN, MAGIC, MAX_KEY};
    let mut head = vec![0u8; HEADER_LEN];
    head[0..4].copy_from_slice(&MAGIC.to_le_bytes());
    head[16] = 1; // op = Put
    head[17..21].copy_from_slice(&(MAX_KEY as u32).to_le_bytes());
    assert!(matches!(
        parse_record(&head),
        Err(WalError::Truncated), // 过了长度闸门，但没有那么多 key 字节 → 截断
    ));
}
