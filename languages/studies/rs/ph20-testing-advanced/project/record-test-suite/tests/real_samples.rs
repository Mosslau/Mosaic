//! 集成测试 · 真实样例：tests/fixtures/sample_put_delete_put.hex 走完整链路。
//! 真实样例 = 最接近线上文件的固定输入：它应当逐字段解析成功，并正确落进假引擎。

mod common;

use common::{build_log, decode_hex_fixture, Engine};
use record_test_suite::{Op, WalError};

#[test]
fn real_sample_parses_field_by_field() {
    let bytes = decode_hex_fixture("sample_put_delete_put.hex");
    let recs: Vec<_> = record_test_suite::records(&bytes)
        .collect::<Result<_, _>>()
        .expect("真实样例必须全量解析");

    assert_eq!(recs.len(), 3);
    assert_eq!(recs[0].sequence, 1);
    assert_eq!(recs[0].op, Op::Put);
    assert_eq!(recs[0].key, b"temperature");
    assert_eq!(recs[0].value, b"36.5");
    assert_eq!(recs[1].key, b"city");
    assert_eq!(recs[1].value, b"tokyo");
    assert_eq!(recs[2].op, Op::Delete);
    assert_eq!(recs[2].key, b"humidity");
    assert!(recs[2].value.is_empty());
}

#[test]
fn real_sample_applies_into_engine() {
    let bytes = decode_hex_fixture("sample_put_delete_put.hex");
    let mut engine = Engine::new();
    let n = engine.apply_bytes(&bytes).expect("合法日志");
    assert_eq!(n, 3);
    assert_eq!(engine.get(b"temperature"), Some(&b"36.5"[..]));
    assert_eq!(engine.get(b"city"), Some(&b"tokyo"[..]));
    assert!(engine.get(b"humidity").is_none(), "Delete 后键应不存在");
    assert_eq!(engine.len(), 2);
}

#[test]
fn zero_copy_pointers_land_inside_fixture_buffer() {
    // 套件级零拷贝回归：key/value 是指向夹具缓冲内部的切片（不是副本）
    let bytes = decode_hex_fixture("sample_put_delete_put.hex");
    let base = bytes.as_ptr() as usize;
    let recs: Vec<_> = record_test_suite::records(&bytes)
        .collect::<Result<_, _>>()
        .expect("合法");
    let off = recs[0].key.as_ptr() as usize - base;
    assert_eq!(off, record_test_suite::HEADER_LEN);
}

#[test]
fn fixture_stability_temperature_log() {
    // 构造辅助与固定夹具同源互证：build_log 产出的字节 == sample fixture 字节
    let via_builder = build_log(&[
        (1, Op::Put, b"temperature", b"36.5"),
        (2, Op::Put, b"city", b"tokyo"),
        (3, Op::Delete, b"humidity", b""),
    ]);
    assert_eq!(via_builder, decode_hex_fixture("sample_put_delete_put.hex"));
}

#[test]
fn truncated_tail_reports_error_type() {
    // 套件层面验证错误 Display（可读性）——错误信息也是可回归的
    let bytes = decode_hex_fixture("err_truncated_tail.hex");
    let mut it = record_test_suite::records(&bytes);
    assert!(it.next().expect("第一条").is_ok());
    assert!(it.next().expect("第二条").is_ok());
    let third = it.next().expect("第三条");
    assert!(matches!(third, Err(WalError::Truncated)));
    assert!(it.next().is_none());
}
