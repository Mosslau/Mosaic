//! 练习 1 参考实现（其一）：异常样例矩阵。
//! 思路：每个「坏输入类别」固化成一个 .hex 数据夹具，用一个 case 表把它们
//! 全部喂给被测对象并断言错误类别。矩阵的好处：新增回归用例 = 加一个文件 + 一行表。

mod common;

use record_parser::{records, WalError};

enum Expect {
    Ok(usize),
    Empty,
    Err(fn(&WalError) -> bool),
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
    // 合法路径
    Case {
        fixture: "valid_put.hex",
        expect: Expect::Ok(1),
    },
    Case {
        fixture: "valid_delete.hex",
        expect: Expect::Ok(1),
    },
    Case {
        fixture: "valid_two_records.hex",
        expect: Expect::Ok(2),
    },
    // 每种错误一个样例
    Case {
        fixture: "err_bad_magic.hex",
        expect: Expect::Err(is_bad_magic),
    },
    Case {
        fixture: "err_unknown_op.hex",
        expect: Expect::Err(is_unknown_op),
    },
    Case {
        fixture: "err_checksum_flip_key.hex",
        expect: Expect::Err(is_checksum),
    },
    Case {
        fixture: "err_klen_overflow.hex",
        expect: Expect::Err(is_too_large),
    },
    Case {
        fixture: "err_vlen_overflow.hex",
        expect: Expect::Err(is_too_large),
    },
    Case {
        fixture: "err_truncated_in_header.hex",
        expect: Expect::Err(is_truncated),
    },
    Case {
        fixture: "err_truncated_in_key.hex",
        expect: Expect::Err(is_truncated),
    },
    // 边界
    Case {
        fixture: "boundary_empty.hex",
        expect: Expect::Empty,
    },
    Case {
        fixture: "boundary_exact_header.hex",
        expect: Expect::Err(is_truncated),
    },
];

#[test]
fn anomaly_matrix_covers_every_fixture() {
    for case in CASES {
        let bytes = common::decode_hex_fixture(case.fixture);
        let mut iter = records(&bytes);
        match case.expect {
            Expect::Ok(n) => {
                let recs: Vec<_> = iter
                    .by_ref()
                    .collect::<Result<_, _>>()
                    .unwrap_or_else(|e| panic!("{} 应解析成功，实际 {e}", case.fixture));
                assert_eq!(recs.len(), n, "{} 应解析出 {n} 条", case.fixture);
            }
            Expect::Empty => {
                assert!(iter.next().is_none(), "{} 应为空日志", case.fixture);
            }
            Expect::Err(classify) => match iter.next() {
                Some(Err(e)) => assert!(classify(&e), "{} 错误类别不符：{e:?}", case.fixture),
                other => panic!("{} 应报错，实际 {other:?}", case.fixture),
            },
        }
    }
}

#[test]
fn content_level_assertions_on_valid_samples() {
    // 不止「条数对」，字段级也要逐一对（防止把坏记录也当成功解析出来）
    let put = common::decode_hex_fixture("valid_put.hex");
    let recs: Vec<_> = records(&put).collect::<Result<_, _>>().expect("合法");
    assert_eq!(recs[0].sequence, 100);
    assert_eq!(recs[0].op, record_parser::Op::Put);
    assert_eq!(recs[0].key, b"alpha");
    assert_eq!(recs[0].value, b"v1");

    let del = common::decode_hex_fixture("valid_delete.hex");
    let recs: Vec<_> = records(&del).collect::<Result<_, _>>().expect("合法");
    assert_eq!(recs[0].op, record_parser::Op::Delete);
    assert_eq!(recs[0].key, b"gone");
    assert!(recs[0].value.is_empty());
}
