//! 设备夹具与构造辅助：真实文件 I/O 全链路 + 任意规模日志的 roundtrip。
//! `TempFile`（Drop 自动清理）保证即使断言失败，临时文件也不会残留。

mod common;

use ex02_test_fixtures::{records, Op};

#[test]
fn temp_file_survives_real_read_and_cleans_itself() {
    // 设备夹具：把内存字节落成真实文件，走与生产 CLI 相同的读盘管线
    let bytes = common::sample_log();
    let tmp = common::TempFile::new("device", &bytes);
    let path = tmp.path().to_path_buf();

    let read_back = std::fs::read(&path).expect("读回临时文件");
    assert_eq!(read_back, bytes);

    let recs: Vec<_> = records(&read_back)
        .collect::<Result<_, _>>()
        .expect("真实文件内容应全量解析");
    assert_eq!(recs.len(), 3);

    drop(tmp); // Drop 即清理
    assert!(!path.exists(), "TempFile Drop 后文件应被删除");
}

#[test]
fn constructor_roundtrip_over_variable_size_keys() {
    // 构造辅助：生成键长 1..=64 的 200 条 record，验证变长布局的解析正确性。
    // entries 持有的是「实际写进日志的 key/value」（Delete 记录 value 恒为空）。
    let mut entries: Vec<(u64, Op, Vec<u8>, Vec<u8>)> = Vec::new();
    for seq in 0..200u64 {
        let key = format!("key-{seq:04}").into_bytes();
        let op = if seq.is_multiple_of(3) {
            Op::Delete
        } else {
            Op::Put
        };
        let value = if op == Op::Delete {
            Vec::new()
        } else {
            vec![b'x'; (seq as usize) % 64 + 1] // value 长度 1..=64
        };
        entries.push((seq, op, key, value));
    }
    let refs: Vec<(u64, Op, &[u8], &[u8])> = entries
        .iter()
        .map(|(seq, op, k, v)| (*seq, *op, k.as_slice(), v.as_slice()))
        .collect();
    let bytes = common::build_log(&refs);

    let recs: Vec<_> = records(&bytes)
        .collect::<Result<_, _>>()
        .expect("构造日志应全量解析");
    assert_eq!(recs.len(), 200);
    for (rec, entry) in recs.iter().zip(&entries) {
        assert_eq!(rec.sequence, entry.0);
        assert_eq!(rec.op, entry.1);
        assert_eq!(rec.key, entry.2.as_slice());
        assert_eq!(rec.value, entry.3.as_slice());
    }
}

#[test]
fn fixture_files_all_exist_and_decode_to_expected_length() {
    // 顺带守护夹具目录本身：缺文件/被误删会在这里立刻暴露
    use ex02_test_fixtures::HEADER_LEN;
    let good = common::decode_hex_fixture("sample_put_delete_put.hex");
    // 三段 record = (25 + 11 + 4) + (25 + 8 + 0) + (25 + 4 + 5)
    assert_eq!(good.len(), 3 * HEADER_LEN + 11 + 4 + 8 + 4 + 5);
    for name in [
        "err_bad_magic.hex",
        "err_bad_op.hex",
        "err_bad_crc.hex",
        "err_klen_huge.hex",
    ] {
        assert_eq!(
            common::decode_hex_fixture(name).len(),
            good.len(),
            "{name} 应只改一个字段，总长不变"
        );
    }
    assert_eq!(
        common::decode_hex_fixture("err_truncated_tail.hex").len(),
        good.len() - 3
    );
}
