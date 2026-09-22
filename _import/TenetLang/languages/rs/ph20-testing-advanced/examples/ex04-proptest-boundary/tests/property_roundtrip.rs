//! 属性 2：结构化 roundtrip —— 构造合法输入验证解析正确性。
//! 手动样例只能测几条记录；这里把「编码 → 解码逐字段相等」写成属性，
//! 让策略在合法域里扫过数千种 key/value/长度组合。

mod common;

use ex04_proptest_boundary::{parse_record, records, HEADER_LEN};
use proptest::prelude::*;

proptest! {
    #![proptest_config(ProptestConfig::with_cases(256))]

    /// 属性：任意合法日志编码后必然逐条解析回来，字段全等、干净收尾。
    #[test]
    fn write_then_parse_roundtrips(entries in common::log()) {
        let bytes = common::encode(&entries);
        let mut it = records(&bytes);
        for (seq, op, key, value) in &entries {
            match it.next() {
                Some(Ok(rec)) => {
                    prop_assert_eq!(rec.sequence, *seq, "seq 不一致");
                    prop_assert_eq!(rec.op, *op, "op 不一致");
                    prop_assert_eq!(rec.key, key.as_slice(), "key 不一致");
                    prop_assert_eq!(rec.value, value.as_slice(), "value 不一致");
                }
                other => {
                    // 构造日志绝不允许解析失败/提前结束
                    panic!("构造的合法日志在第 {seq} 条解析异常：{other:?}")
                }
            }
        }
        prop_assert!(it.next().is_none(), "日志解析完后迭代器必须干净结束");
    }

    /// 属性：单条 record + 任意后缀 → 解析器只消费自己那一段，
    /// used 恰好等于字段总长，剩余字节与后缀逐字相同（不读穿、不吞后缀）。
    #[test]
    fn record_consumes_only_its_own_fields((bytes, suffix) in common::record_with_suffix()) {
        let (rec, used) = match parse_record(&bytes) {
            Ok(v) => v,
            Err(e) => panic!("带合法前缀+后缀的输入不应报错：{e:?}"),
        };
        prop_assert_eq!(used, HEADER_LEN + rec.key.len() + rec.value.len());
        prop_assert_eq!(
            &bytes[used..],
            suffix.as_slice(),
            "record 之后必须原样留下后缀字节"
        );
    }
}
