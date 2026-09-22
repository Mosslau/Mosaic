//! sol-02（其三）：损坏即停 —— 引擎只吃到损坏点之前的前缀。
//! 这是 WAL 恢复语义的集成回归：损坏点之后的数据不可信，绝不能继续应用。

mod common;

use common::{build_log, Engine};
use record_parser::{Op, WalError};

#[test]
fn corruption_stops_before_touching_later_records() {
    let bytes = build_log(&[
        (1, Op::Put, b"a", b"1"),
        (2, Op::Put, b"b", b"22"), // ← 在这条上翻转一个 key 字节制造损坏
        (3, Op::Put, b"c", b"333"),
    ]);
    let mut corrupted = bytes.clone();
    // 第二条 payload（key||value）区起点 = 第一条全长 + HEADER_LEN(25)，再 +2 落在其内；
    // key/value 都进 CRC，翻转任意一字节都会触发 ChecksumMismatch
    let first_len = 25 + 1 + 1; // header + key "a"(1B) + value "1"(1B)
    corrupted[first_len + 25 + 2] ^= 0xFF;

    let mut engine = Engine::new();
    let err = engine
        .apply_bytes(&corrupted)
        .expect_err("第二条应校验失败");
    assert!(matches!(err, WalError::ChecksumMismatch { .. }));
    assert_eq!(engine.applied().len(), 1, "只应用了第一条");
    assert_eq!(engine.get(b"a"), Some(&b"1"[..]));
    assert!(engine.get(b"b").is_none(), "损坏的 record 不得进入引擎");
    assert!(
        engine.get(b"c").is_none(),
        "损坏点之后的 record 不得进入引擎"
    );
}
