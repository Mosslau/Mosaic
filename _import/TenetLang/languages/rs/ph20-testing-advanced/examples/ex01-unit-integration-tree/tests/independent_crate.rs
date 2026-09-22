//! 第二个集成测试文件：演示 tests/*.rs「各自独立成 crate」。
//! 它与 file_roundtrip.rs 平行：不共享任何符号（连 mod common 都要重新声明），
//! 各自独立编译、可被 cargo 单独跑：`cargo test --test independent_crate`。

mod common;

use ex01_unit_integration_tree::{records, WalError, HEADER_LEN};

#[test]
fn truncated_prefix_always_reports_truncated() {
    let full = common::sample_log_bytes();
    // 把日志从 0 到全长逐字节截短：无论在哪一刀切下，解析要么成功要么报 Truncated，
    // 绝不 panic、绝无其他错误变体 —— 这是对 ph19「长度不足是合法状态」纪律的集成回归。
    for cut in 0..full.len() {
        match records(&full[..cut]).next() {
            None => { /* cut == 0：空输入直接干净结束 */ }
            Some(Ok(_)) => { /* 截在一条完整 record 之后：合法 */ }
            Some(Err(e)) => {
                assert_eq!(
                    e,
                    WalError::Truncated,
                    "从 {cut} 字节处截断应报 Truncated，实际 {e:?}"
                );
            }
        }
    }
}

#[test]
fn private_items_are_not_visible_from_integration_tests() {
    // 集成测试只能见 pub API；若这里想碰 `crc32_combine` 等私有项，编译期即失败。
    // （本测试本身无断言需求，仅作「可见性边界」的文档化示例：pub 面即测试面。）
    let _ = HEADER_LEN; // pub const 可见
    assert_eq!(HEADER_LEN, 25);
}
