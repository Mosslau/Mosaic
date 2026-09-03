//! record-test-suite —— ph20 阶段项目：record 解析测试套件（真实样例 + 错误样例 + 基准测试）。
//!
//! 被测对象是 ph19 引入的迷你 WAL record 解析器（本 crate 的 `record` 模块，
//! 结构复刻 ph19 阶段项目 wal-record-parser）。本阶段不写新解析逻辑，而是把
//! ph20 学到的**测试体系**全部压在同一个被测对象上：
//!
//! | 层 | 载体 | 内容 |
//! |----|------|------|
//! | 单元测试 | src/record.rs 内 `#[cfg(test)]` | CRC 向量、roundtrip、零拷贝指针、篡改拦截、截断矩阵 |
//! | 集成测试 | tests/real_samples.rs | 真实样例文件 → 解析 → 应用，字段级断言 |
//! | 异常矩阵 | tests/anomaly_matrix.rs | tests/fixtures/*.hex 错误样例逐个断言错误类别 + 逐截断点全扫 |
//! | 属性测试 | tests/property.rs | proptest：任意字节不 panic、roundtrip、Delete 空 value |
//! | 基准测试 | benches/parse_bench.rs | criterion：零拷贝 vs 快照复制、噪声控制、基线对比 |
//! | doctest | 本文件下方示例 | 文档示例即测试 |
//!
//! 验收与全部命令见 `project/README.md`。
//!
//! ```
//! use record_test_suite::{records, Op, WalWriter};
//!
//! let mut w = WalWriter::new();
//! w.append(1, Op::Put, b"temperature", b"36.5");
//! w.append(2, Op::Delete, b"humidity", b"");
//! let n = records(w.as_bytes())
//!     .collect::<Result<Vec<_>, _>>()
//!     .expect("合法日志")
//!     .len();
//! assert_eq!(n, 2);
//! ```

mod record;

pub use record::{
    parse_record, records, Op, Record, WalError, WalWriter, HEADER_LEN, MAGIC, MAX_KEY, MAX_VALUE,
};

/// 被测对象白名单检查：本套件只测 `record` 模块暴露的稳定 API，不测内部实现细节。
pub fn api_surface() -> &'static [&'static str] {
    &[
        "MAGIC",
        "HEADER_LEN",
        "MAX_KEY",
        "MAX_VALUE",
        "Op",
        "Record",
        "WalError",
        "WalWriter",
        "parse_record",
        "records",
    ]
}
