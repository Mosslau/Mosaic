//! 集成测试 · 异常样例矩阵 + 逐截断点全扫（roadmap ph20 练习 1 在套件中的固化形态）。

mod common;

use common::decode_hex_fixture;
use record_test_suite::{records, WalError};

enum Expect {
    Ok(usize),
    Empty,
    Err(fn(&WalError) -> bool),
    OkThenErr(usize, fn(&WalError) -> bool),
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
    Case {
        fixture: "sample_put_delete_put.hex",
        expect: Expect::Ok(3),
    },
    Case {
        fixture: "err_bad_magic.hex",
        expect: Expect::Err(is_bad_magic),
    },
    Case {
        fixture: "err_unknown_op.hex",
        expect: Expect::Err(is_unknown_op),
    },
    Case {
        fixture: "err_checksum_flip.hex",
        expect: Expect::Err(is_checksum),
    },
    Case {
        fixture: "err_klen_overflow.hex",
        expect: Expect::Err(is_too_large),
    },
    Case {
        fixture: "err_truncated_tail.hex",
        expect: Expect::OkThenErr(2, is_truncated),
    },
    Case {
        fixture: "boundary_empty.hex",
        expect: Expect::Empty,
    },
];

#[test]
fn anomaly_matrix_covers_all_fixtures() {
    for case in CASES {
        let bytes = decode_hex_fixture(case.fixture);
        let mut it = records(&bytes);
        match case.expect {
            Expect::Ok(n) => {
                let recs: Vec<_> = it
                    .by_ref()
                    .collect::<Result<_, _>>()
                    .unwrap_or_else(|e| panic!("{} 应解析成功：{e}", case.fixture));
                assert_eq!(recs.len(), n);
            }
            Expect::Empty => assert!(it.next().is_none(), "{} 应为空日志", case.fixture),
            Expect::Err(classify) => match it.next() {
                Some(Err(e)) => {
                    assert!(classify(&e), "{} 错误类别不符：{e:?}", case.fixture)
                }
                other => panic!("{} 应报错：{other:?}", case.fixture),
            },
            Expect::OkThenErr(n, classify) => {
                for _ in 0..n {
                    it.next().expect("应还有 record").expect("前段合法");
                }
                match it.next() {
                    Some(Err(e)) => {
                        assert!(classify(&e), "{} 错误类别不符：{e:?}", case.fixture)
                    }
                    other => panic!("{} 第 {n} 条后应报错：{other:?}", case.fixture),
                }
                assert!(it.next().is_none(), "{} 报错后必须终止", case.fixture);
            }
        }
    }
}

#[test]
fn every_truncation_point_is_safe_and_monotonic() {
    // 对真实样例日志做逐字节截断扫描：只能「Ok…Ok + Truncated + 终止」或全 Ok
    let full = decode_hex_fixture("sample_put_delete_put.hex");
    for cut in 0..full.len() {
        let mut it = records(&full[..cut]);
        let mut stopped = false;
        while let Some(item) = it.next() {
            match item {
                Ok(_) => assert!(!stopped, "出错后不得继续吐 Ok"),
                Err(e) => {
                    assert_eq!(e, WalError::Truncated, "截断点 {cut}：{e:?}");
                    stopped = true;
                    assert!(it.next().is_none(), "截断点 {cut} 报错后必须终止");
                }
            }
        }
    }
}

#[test]
fn single_byte_flips_never_panic_and_stay_classified() {
    // 在真实样例上逐字节翻转：每处翻转都不得 panic；错误类别必须落在已知集合里
    let full = decode_hex_fixture("sample_put_delete_put.hex");
    for pos in 0..full.len() {
        let mut mutated = full.clone();
        mutated[pos] ^= 0x01;
        let _ = records(&mutated).collect::<Result<Vec<_>, _>>();
        // 不 panic 即通过；collect 返回的 Err 内部必然是 WalError（由类型保证）
    }
}
