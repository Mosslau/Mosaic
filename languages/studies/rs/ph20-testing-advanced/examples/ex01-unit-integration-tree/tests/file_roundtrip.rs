//! 集成测试：文件级全链路（tests/ 下每个 .rs 是独立 crate，本文件是其中一个）。
//! 场景：WalWriter 产出字节 → 落成真实文件 → `std::fs::read` 读回 →
//! `records` 零拷贝重放。只使用被测 crate 的 **pub API** —— 集成测试测的是契约。

mod common; // 每个 tests/*.rs 各自 `mod common;`（见 tests/common/mod.rs 的说明）

use ex01_unit_integration_tree::{records, Op};
use std::fs;

#[test]
fn file_roundtrip_replays_all_records() {
    let bytes = common::sample_log_bytes();
    let path = common::write_temp_wal("roundtrip", &bytes);

    // 真实文件 I/O 全链路
    let read_back = fs::read(&path).expect("读回临时 WAL（测试上下文）");
    assert_eq!(read_back, bytes, "文件内容与写入一致");

    let parsed: Vec<_> = records(&read_back)
        .collect::<Result<_, _>>()
        .expect("合法日志应全部解析成功");
    assert_eq!(parsed.len(), 3);
    assert_eq!(parsed[0].sequence, 1);
    assert_eq!(parsed[0].key, b"temperature");
    assert_eq!(parsed[1].op, Op::Delete);
    assert_eq!(parsed[2].key, b"city");

    fs::remove_file(&path).expect("清理临时 WAL");
}

#[test]
fn zero_copy_pointers_point_into_file_buffer() {
    // 集成层也验证零拷贝：解析出的 key 指针必须落在「读回的文件缓冲」内部
    let path = common::write_temp_wal("zerocopy", &common::sample_log_bytes());
    let read_back = fs::read(&path).expect("读回临时 WAL");
    let base = read_back.as_ptr() as usize;

    let recs: Vec<_> = records(&read_back)
        .collect::<Result<_, _>>()
        .expect("解析成功");
    assert_eq!(recs[0].key.as_ptr() as usize - base, 25); // 第一条 key 在头部 25 字节后
    fs::remove_file(&path).expect("清理临时 WAL");
}
