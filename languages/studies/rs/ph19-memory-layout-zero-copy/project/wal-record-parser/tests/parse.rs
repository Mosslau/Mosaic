//! 集成测试：把 WalWriter 产出的日志落成真实文件，经 `std::fs::read` 读回，
//! 走与 `main.rs --file` 完全相同的「整读 → 零拷贝解析」管线，验证全链路正确。
//! 临时文件放系统临时目录，测完即删，不污染仓库。

use std::fs;
use std::path::PathBuf;
use wal_record_parser::{records, Op, WalError, WalWriter};

/// 在系统临时目录建一个独占路径的 WAL 文件，返回 (路径, 文件字节)。
/// `tag` 让每个测试的文件名唯一，避免并行测试互相覆盖/删除。
fn write_temp_wal(tag: &str) -> (PathBuf, Vec<u8>) {
    let mut w = WalWriter::new();
    w.append(1, Op::Put, b"temperature", b"36.5");
    w.append(2, Op::Delete, b"humidity", b"");
    w.append(3, Op::Put, b"city", b"tokyo");

    let mut path = std::env::temp_dir();
    path.push(format!("ph19-wal-{}-{tag}.wal", std::process::id()));
    fs::write(&path, w.as_bytes()).expect("写入临时 WAL");
    (path, w.as_bytes().to_vec())
}

#[test]
fn file_roundtrip_replays_all_records() {
    let (path, bytes) = write_temp_wal("roundtrip");
    let read_back = fs::read(&path).expect("读回临时 WAL");
    assert_eq!(read_back, bytes, "文件内容与写入一致");

    let parsed: Vec<_> = records(&read_back)
        .collect::<Result<_, _>>()
        .expect("解析成功");
    assert_eq!(parsed.len(), 3);
    assert_eq!(parsed[0].sequence, 1);
    assert_eq!(parsed[0].key, b"temperature");
    assert_eq!(parsed[1].op, Op::Delete);
    assert_eq!(parsed[2].key, b"city");
    fs::remove_file(&path).expect("清理临时 WAL");
}

#[test]
fn corrupted_file_reports_error_not_panic() {
    let (path, mut bytes) = write_temp_wal("corrupted");
    bytes[HEADER_OFFSET_OF_FIRST_KEY + 1] ^= 0x01; // 翻转第一条 key 的一个字节
    fs::write(&path, &bytes).expect("覆写损坏 WAL");

    let read_back = fs::read(&path).expect("读回损坏 WAL");
    // 期待：第一条即报 ChecksumMismatch（不用 expect-on-Err 形式，便于测试里展开失败信息）
    let first = records(&read_back).next().expect("至少一条");
    match first {
        Err(err) => {
            assert!(
                matches!(err, WalError::ChecksumMismatch { .. }),
                "应报校验失败，实际 {err:?}"
            );
        }
        Ok(rec) => panic!("损坏文件不应解析出 record：{rec:?}"),
    }
    fs::remove_file(&path).expect("清理临时 WAL");
}

/// 第一条 key 的起点：HEADER_LEN（magic/crc/seq/op/klen/vlen 共 25 字节）。
const HEADER_OFFSET_OF_FIRST_KEY: usize = 25;
