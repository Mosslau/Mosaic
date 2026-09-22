//! 数据夹具矩阵：把 tests/fixtures/*.hex 里的每个样例喂给解析器，逐个断言
//! 「该 Ok 的 Ok、该报哪类错就报哪类错」。Rust 没有内建的参数化测试，
//! 用「case 表 + 一个驱动函数」实现同样的矩阵效果——新增样例只需往表里加一行。
//!
//! 这里展示的正是 roadmap ph20 练习「为解析器加入异常样例测试」的形态：
//! 每类坏输入一个固定样例文件（可 diff、可回归），配一行式的断言。

mod common;

use ex02_test_fixtures::{records, WalError};

/// 断言方向：文件应干净解析出 N 条 / 应为空 / 首错应为某类错误。
enum Expect {
    Ok(usize),                               // 期望完整解析出 N 条 record
    Empty,                                   // 期望零 record 干净结束（空文件）
    Err(fn(&WalError) -> bool),              // 期望首条即报该类错误
    OkThenErr(usize, fn(&WalError) -> bool), // 期望前 N 条合法、第 N+1 条报该类错误
}

struct Case {
    fixture: &'static str,
    expect: Expect,
}

fn is_bad_magic(e: &WalError) -> bool {
    matches!(e, WalError::BadMagic(_))
}
fn is_unknown_op(e: &WalError) -> bool {
    matches!(e, WalError::UnknownOp(_))
}
fn is_checksum(e: &WalError) -> bool {
    matches!(e, WalError::ChecksumMismatch { .. })
}
fn is_truncated(e: &WalError) -> bool {
    matches!(e, WalError::Truncated)
}
fn is_too_large(e: &WalError) -> bool {
    matches!(e, WalError::TooLarge { .. })
}

const CASES: &[Case] = &[
    // —— 真实样例 ——
    Case {
        fixture: "sample_put_delete_put.hex",
        expect: Expect::Ok(3),
    },
    // —— 错误样例矩阵（异常样例测试）——
    Case {
        fixture: "err_bad_magic.hex",
        expect: Expect::Err(is_bad_magic),
    },
    Case {
        fixture: "err_bad_op.hex",
        expect: Expect::Err(is_unknown_op),
    },
    Case {
        fixture: "err_bad_crc.hex",
        expect: Expect::Err(is_checksum),
    },
    Case {
        fixture: "err_truncated_tail.hex",
        expect: Expect::OkThenErr(2, is_truncated), // 前两条合法、第三条截断
    },
    Case {
        fixture: "err_klen_huge.hex",
        expect: Expect::Err(is_too_large),
    },
    // —— 边界样例 ——
    Case {
        fixture: "empty.hex",
        expect: Expect::Empty,
    },
];

#[test]
fn fixture_matrix_asserts_each_sample() {
    for case in CASES {
        let bytes = common::decode_hex_fixture(case.fixture);
        let mut iter = records(&bytes); // 被测对象：只走 pub API
        match &case.expect {
            Expect::Ok(n) => {
                let recs: Result<Vec<_>, _> = iter.by_ref().collect();
                let recs = recs.unwrap_or_else(|e| panic!("{} 应解析成功，实际 {e}", case.fixture));
                assert_eq!(recs.len(), *n, "{} 应解析出 {n} 条", case.fixture);
            }
            Expect::Empty => {
                assert!(
                    iter.next().is_none(),
                    "{} 应为空日志（干净结束）",
                    case.fixture
                );
            }
            Expect::Err(classify) => match iter.next() {
                Some(Err(e)) => {
                    assert!(classify(&e), "{} 错误类别不符：{e:?}", case.fixture)
                }
                other => panic!("{} 应首条即报错，实际 {other:?}", case.fixture),
            },
            Expect::OkThenErr(n, classify) => {
                for _ in 0..*n {
                    iter.next().expect("应还能吐 record").expect("前段应合法");
                }
                match iter.next() {
                    Some(Err(e)) => {
                        assert!(classify(&e), "{} 错误类别不符：{e:?}", case.fixture)
                    }
                    other => panic!("{} 第 {} 条后应报错，实际 {other:?}", case.fixture, n),
                }
                assert!(iter.next().is_none(), "{} 出错后迭代必须终止", case.fixture);
            }
        }
    }
}

#[test]
fn good_sample_parses_to_expected_records() {
    // 单独盯一遍真实样例的内容级断言（不只是条数）：字段、op、key/value 逐一对齐
    let bytes = common::decode_hex_fixture("sample_put_delete_put.hex");
    let recs: Vec<_> = records(&bytes)
        .collect::<Result<_, _>>()
        .expect("真实样例必须全量解析");
    assert_eq!(recs.len(), 3);
    assert_eq!(recs[0].sequence, 1);
    assert_eq!(recs[0].key, b"temperature");
    assert_eq!(recs[0].value, b"36.5");
    assert_eq!(recs[1].op, ex02_test_fixtures::Op::Delete);
    assert_eq!(recs[1].key, b"humidity");
    assert_eq!(recs[2].sequence, 3);
    assert_eq!(recs[2].key, b"city");
    assert_eq!(recs[2].value, b"tokyo");
}
