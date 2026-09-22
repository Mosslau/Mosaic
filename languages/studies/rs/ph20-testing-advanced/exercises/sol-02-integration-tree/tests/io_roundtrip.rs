//! sol-02（其二）：真实文件 I/O + 假引擎应用的集成全链路。
//! 与生产管线一致：字节落盘 → 整读 → 解析 → 应用到引擎。

mod common;

use common::{build_log, Engine, TempFile};
use record_parser::Op;

#[test]
fn file_roundtrip_into_engine() {
    let bytes = build_log(&[
        (1, Op::Put, b"temperature", b"36.5"),
        (2, Op::Put, b"city", b"tokyo"),
    ]);
    let tmp = TempFile::new("engine", &bytes);
    let read_back = std::fs::read(tmp.path()).expect("读回临时文件");

    let mut engine = Engine::new();
    let n = engine.apply_bytes(&read_back).expect("合法日志");
    assert_eq!(n, 2);
    assert_eq!(engine.get(b"temperature"), Some(&b"36.5"[..]));
    assert_eq!(engine.get(b"city"), Some(&b"tokyo"[..]));
}

#[test]
fn temp_file_is_cleaned_up() {
    let tmp = TempFile::new("cleanup", b"unused");
    let path = tmp.path().to_path_buf();
    assert!(path.exists());
    drop(tmp);
    assert!(!path.exists(), "Drop 后设备夹具应自动清理");
}
