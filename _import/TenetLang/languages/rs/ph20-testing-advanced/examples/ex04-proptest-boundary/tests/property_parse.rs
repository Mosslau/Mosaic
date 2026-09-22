//! 属性 1：任意字节轰炸解析器 —— 永不 panic、错误类别合法、截断语义单调。
//! 这类「喂什么都行」的属性是手写样例矩阵补不齐的：256 个用例 × 0..512 字节
//! 的随机字节流，覆盖手写 fixture 想不到的错位、长度怪值。

mod common;

use ex04_proptest_boundary::{parse_record, records, WalError, HEADER_LEN};
use proptest::prelude::*;

proptest! {
    #![proptest_config(ProptestConfig::with_cases(256))]

    /// 属性：任何字节输入都不 panic（panic 即测试失败，proptest 会收缩出最小反例）。
    #[test]
    fn never_panics_on_arbitrary_bytes(bytes in common::any_bytes()) {
        // records 迭代 + collect：无论中间报什么错都吞进 Result，绝不允许 panic 冒头
        let _ = records(&bytes).collect::<Result<Vec<_>, _>>();
        // 单条视角也一样
        let _ = parse_record(&bytes);
    }

    /// 属性：错误只来自五类合法错误（不会出现「别的」失败形态）。
    #[test]
    fn errors_stay_within_known_variants(bytes in common::any_bytes()) {
        if let Err(e) = parse_record(&bytes) {
            prop_assert!(
                matches!(
                    e,
                    WalError::BadMagic(_)
                        | WalError::Truncated
                        | WalError::ChecksumMismatch { .. }
                        | WalError::UnknownOp(_)
                        | WalError::TooLarge { .. }
                ),
                "未知错误形态出现：{e:?}"
            );
        }
    }

    /// 边界属性：不足 25 字节的头部一律 Truncated；恰好 25 字节（魔数对）才谈得上往下走。
    #[test]
    fn sub_header_input_is_always_truncated(bytes in prop::collection::vec(any::<u8>(), 0..HEADER_LEN)) {
        if bytes.len() < HEADER_LEN {
            prop_assert_eq!(
                parse_record(&bytes).err(),
                Some(WalError::Truncated),
                "长度 {} < HEADER_LEN 必须报 Truncated",
                bytes.len()
            );
        }
    }
}

/// 顺带验证：records 迭代器本身对「一段合法日志的任意前缀」不会 panic 于中途越界。
#[test]
fn records_never_panics_on_any_prefix_of_valid_log() {
    let mut w = ex04_proptest_boundary::WalWriter::new();
    for seq in 0..8u64 {
        w.append(seq, ex04_proptest_boundary::Op::Put, b"k", b"v");
    }
    let full = w.as_bytes().to_vec();
    for cut in 0..=full.len() {
        // 每刀都吞掉错误，唯一要求：不 panic
        let _ = records(&full[..cut]).collect::<Result<Vec<_>, _>>();
    }
}
