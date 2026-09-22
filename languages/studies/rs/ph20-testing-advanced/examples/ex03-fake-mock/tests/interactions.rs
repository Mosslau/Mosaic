//! mock 与 fake 的对照测试：同一被测对象 `replay_to`，注入两种测试替身。
//!
//! - `MemoryStore`（fake，库内实现）：完整行为，断言「结果对不对」；
//! - `MockStore`（手动 mock，本文件实现）：记录调用、可脚本化失败，断言「协议对不对」。
//!
//! 手动 mock 的结构其实很机械：记录调用日志 + 预设返回。生产项目里这段样板
//! 通常交给 `mockall`（`#[automock]` 自动生成同名结构，见主文档 3.4）——
//! 这里手写一遍是为了看清 mock 的**本质**就是「可断言的调用记录器」。

use ex03_fake_mock::{
    replay_to, Entry, MemoryStore, Op, ReplayError, Store, StoreError, WalWriter,
};

fn sample_log() -> Vec<u8> {
    let mut w = WalWriter::new();
    w.append(1, Op::Put, b"temperature", b"36.5");
    w.append(2, Op::Delete, b"humidity", b"");
    w.append(3, Op::Put, b"city", b"tokyo");
    w.as_bytes().to_vec()
}

/// 记录一次 apply 调用的参数。
#[derive(Debug, Clone, PartialEq, Eq)]
struct Call {
    op: Op,
    seq: u64,
    key: Vec<u8>,
    value: Vec<u8>,
}

/// 手动 mock：把每次 `apply` 的参数记进 `calls`，并支持「第 k 次调用注入失败」。
#[derive(Debug, Default)]
struct MockStore {
    calls: Vec<Call>,
    fail_on: Option<usize>,
}

impl MockStore {
    fn failing_on(mut self, nth: usize) -> Self {
        self.fail_on = Some(nth);
        self
    }

    fn calls(&self) -> &[Call] {
        &self.calls
    }
}

impl Store for MockStore {
    fn apply(&mut self, op: Op, seq: u64, key: &[u8], value: &[u8]) -> Result<(), StoreError> {
        // 先记录（即使这次失败，调用确实发生过）
        self.calls.push(Call {
            op,
            seq,
            key: key.to_vec(),
            value: value.to_vec(),
        });
        if let Some(nth) = self.fail_on {
            if self.calls.len() == nth {
                return Err(StoreError("磁盘已满（mock 注入）".to_owned()));
            }
        }
        Ok(())
    }
}

#[test]
fn fake_asserts_behavior_happy_path() {
    // fake 测行为：replay 后 MemoryStore 里的内容应当正好是那三段
    let log = sample_log();
    let mut store = MemoryStore::new();
    let n = replay_to(&mut store, &log).expect("合法日志");
    assert_eq!(n, 3);

    let entries: Vec<(u64, &[u8])> = store
        .entries()
        .iter()
        .map(|e| (e.seq, e.key.as_slice()))
        .collect();
    assert_eq!(
        entries,
        vec![
            (1, &b"temperature"[..]),
            (2, &b"humidity"[..]),
            (3, &b"city"[..])
        ]
    );
}

#[test]
fn mock_asserts_interaction_protocol() {
    // mock 测协议：不仅结果对，还要「按序、恰好、带对参数」调用
    let log = sample_log();
    let mut mock = MockStore::default();
    replay_to(&mut mock, &log).expect("合法日志");

    let calls = mock.calls();
    assert_eq!(calls.len(), 3, "恰好调用 3 次，不多不少");
    assert_eq!(
        (calls[0].seq, calls[0].op, calls[0].key.as_slice()),
        (1, Op::Put, &b"temperature"[..])
    );
    assert_eq!(calls[0].value.as_slice(), b"36.5");
    // Delete 记录：value 恒为空是写入端约定，mock 能抓「传错 value」这类实现 bug
    assert_eq!((calls[1].seq, calls[1].op), (2, Op::Delete));
    assert!(calls[1].value.is_empty());
    assert_eq!(calls[2].key.as_slice(), b"city");
}

#[test]
fn mock_and_fake_agree_on_happy_path() {
    // 交叉验证：同一日志下，fake 的「应用结果」与 mock 的「调用记录」必须一一对应
    let log = sample_log();
    let mut store = MemoryStore::new();
    let mut mock = MockStore::default();
    replay_to(&mut store, &log).expect("fake");
    replay_to(&mut mock, &log).expect("mock");

    let as_entry = |c: &Call| Entry {
        op: c.op,
        seq: c.seq,
        key: c.key.clone(),
        value: c.value.clone(),
    };
    assert_eq!(
        store.entries(),
        mock.calls()
            .iter()
            .map(as_entry)
            .collect::<Vec<_>>()
            .as_slice()
    );
}

#[test]
fn mock_injects_failure_and_replay_stops() {
    // 失败注入：第 2 次 apply 报「磁盘满」→ replay 必须停在 seq=2，
    // 不能继续调第 3 次（WAL 恢复遇到存储故障就停，这正是可测试设计要暴露的语义）
    let log = sample_log();
    let mut mock = MockStore::default().failing_on(2);
    let err = replay_to(&mut mock, &log).expect_err("第 2 次应用应失败");

    match err {
        ReplayError::Apply { seq, source, .. } => {
            assert_eq!(seq, 2);
            assert!(source.to_string().contains("磁盘已满"));
        }
        other => panic!("应报 Apply 错误，实际 {other:?}"),
    }
    assert_eq!(mock.calls().len(), 2, "失败后不得再尝试后续 record");
}

#[test]
fn truncated_log_applies_prefix_then_reports_parse_error() {
    // 解析层错误（截断）走 ReplayError::Parse；已应用的前缀保留在 store/mock 里
    let log = sample_log();
    let cut_len = log.len() - 3; // 砍掉第三条 value 的 3 字节
    let mut store = MemoryStore::new();
    let err = replay_to(&mut store, &log[..cut_len]).expect_err("应解析失败");

    assert!(matches!(
        err,
        ReplayError::Parse(ex03_fake_mock::WalError::Truncated)
    ));
    assert_eq!(store.entries().len(), 2, "前两条已应用，第三条应报错停止");
}
