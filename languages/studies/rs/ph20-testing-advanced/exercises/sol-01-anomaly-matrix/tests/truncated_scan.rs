//! 练习 1 参考实现（其二）：逐截断点全量扫描。
//! 「手工挑几个截断长度」永远会漏：把一段合法两段日志的**每一个**截断点都试一遍，
//! 语义必须满足 —— 只吐出完整 record 前缀；遇截断报 Truncated 并终止；绝不 panic。
//! 这相当于用确定性穷举覆盖了 proptest 里那部分「长度边界」的职责。

mod common;

use record_parser::{records, WalError};

#[test]
fn every_truncation_point_of_two_record_log_is_safe() {
    let full = common::decode_hex_fixture("valid_two_records.hex");
    // 先确认全长能解析出 2 条（前置条件，避免「测试自身写错」把结果带偏）
    assert_eq!(
        records(&full)
            .collect::<Result<Vec<_>, _>>()
            .expect("全长应合法")
            .len(),
        2
    );

    for cut in 0..full.len() {
        let mut iter = records(&full[..cut]);
        let mut parsed = 0usize;
        // 只允许两种结局：要么全 Ok（切点在整条 record 之后），
        // 要么「若干 Ok 后一个 Truncated，然后立即结束」
        let mut stopped_with_truncated = false;
        while let Some(item) = iter.next() {
            match item {
                Ok(_) => {
                    assert!(!stopped_with_truncated, "出错后不得继续吐 Ok");
                    parsed += 1;
                }
                Err(e) => {
                    assert_eq!(
                        e,
                        WalError::Truncated,
                        "截断点 {cut} 处应报 Truncated，实际 {e:?}"
                    );
                    stopped_with_truncated = true;
                    assert!(
                        iter.next().is_none(),
                        "截断点 {cut}：报错后迭代必须立即终止"
                    );
                }
            }
        }
        // 解析出的条数不会超过全长能容纳的 2 条
        assert!(
            parsed <= 2,
            "截断点 {cut} 解析出 {parsed} 条（超过全长记录数）"
        );
    }
}
