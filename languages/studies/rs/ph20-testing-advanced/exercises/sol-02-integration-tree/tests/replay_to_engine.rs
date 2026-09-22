//! sol-02（其一）：字节 → 假引擎的语义链路（不经过真实 I/O，纯内存契约测试）。
//! 同一份日志断言三件事：操作顺序、Put 覆盖、Delete 删除。

mod common;

use common::{build_log, Engine};
use record_parser::Op;

#[test]
fn replay_applies_ops_in_log_order() {
    let mut engine = Engine::new();
    let log = build_log(&[
        (1, Op::Put, b"city", b"tokyo"),
        (2, Op::Put, b"country", b"jp"),
        (3, Op::Delete, b"city", b""),
    ]);
    let n = engine.apply_bytes(&log).expect("合法日志");
    assert_eq!(n, 3);

    // 操作顺序逐条可查
    let ops: Vec<(u64, &[u8])> = engine
        .applied()
        .iter()
        .map(|a| (a.seq, a.key.as_slice()))
        .collect();
    assert_eq!(
        ops,
        vec![(1, &b"city"[..]), (2, &b"country"[..]), (3, &b"city"[..])]
    );
    // 最终态：city 被删除，country 还在
    assert!(engine.get(b"city").is_none());
    assert_eq!(engine.get(b"country"), Some(&b"jp"[..]));
    assert_eq!(engine.len(), 1);
}

#[test]
fn put_overwrites_and_delete_removes() {
    let mut engine = Engine::new();
    let log = build_log(&[
        (1, Op::Put, b"k", b"v1"),
        (2, Op::Put, b"k", b"v2"),  // 覆盖
        (3, Op::Delete, b"k", b""), // 删除
        (4, Op::Put, b"k", b"v3"),  // 重建
    ]);
    engine.apply_bytes(&log).expect("合法日志");
    assert_eq!(engine.get(b"k"), Some(&b"v3"[..]));
    assert_eq!(engine.applied().len(), 4);
}

#[test]
fn delete_on_missing_key_is_noop_but_recorded() {
    let mut engine = Engine::new();
    let log = build_log(&[(1, Op::Delete, b"ghost", b"")]);
    engine.apply_bytes(&log).expect("合法日志");
    assert!(engine.is_empty());
    assert_eq!(engine.applied().len(), 1, "操作被记录（语义上可回放）");
}
