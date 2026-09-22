//! WAL（Write-Ahead Log）record 解析库：字节 → 结构化 record 的安全 + 零拷贝路径。
//!
//! 本 crate 是 **examples/ex02 的 test fixtures 演示被测对象**——结构复刻自
//! ph19 阶段项目 `wal-record-parser`，格式与 ph19 主文档 3.8 一致（字段一律小端）。
//! 看点是**测试数据从哪来**：固定样例落成 tests/fixtures/*.hex 数据文件（文本可读、
//! 可 diff），测试从文件解码后喂解析器；动态构造交给 tests/common 的构造辅助；
//! 需要真实 I/O 的用例把字节写进系统临时目录（设备夹具）。
//!
//! # 格式（教学简化）
//!
//! ```text
//! [magic: u32] = "WAL1"  定位错位/异格式
//! [crc: u32]            对 key||value 求 CRC32（IEEE），先校验再信任
//! [seq: u64]            单调序列号
//! [op: u8]              1=Put, 2=Delete
//! [klen: u32][key]      长度前缀 + 变长 key
//! [vlen: u32][value]    长度前缀 + 变长 value（Delete 记录 vlen == 0）
//! ```
//!
//! # 安全纪律（ph19 主文档 3.7/3.8 复述）
//!
//! - 解析不 panic：每步 `get` 区间检查 + `try_into` 定长数组；
//! - `parse_record` 返回的 `key`/`value` 是**借用输入的切片**，全程零分配；
//! - 魔数先行（防错位）、CRC 次之（防损坏）、业务字段最后才被信任。
//!
//! # 使用示例（同时是本 crate 的 doctest，`cargo test --doc` 会跑它）
//!
//! ```rust
//! use ex02_test_fixtures::{records, Op, WalWriter};
//!
//! let mut w = WalWriter::new();
//! w.append(1, Op::Put, b"temperature", b"36.5");
//! w.append(2, Op::Delete, b"humidity", b"");
//!
//! let parsed: Vec<_> = records(w.as_bytes())
//!     .collect::<Result<_, _>>()
//!     .expect("合法日志应全部解析成功");
//! assert_eq!(parsed.len(), 2);
//! assert_eq!(parsed[0].key, b"temperature");
//! assert_eq!(parsed[1].op, Op::Delete);
//! ```
//!
//! # 零拷贝边界（诚实说明）
//!
//! 解析本身不复制；但「迭代多条 record」用 [`records`] 逐个返回借用视图。
//! 若调用方要把 key/value 存进引擎（如 ph25 的 MemTable），复制发生在调用方，
//! 那是所有权交接点上的必要复制，不是解析器的浪费。

use std::error::Error;
use std::fmt;

/// 魔数 `b"WAL1"`（小端落盘）。
pub const MAGIC: u32 = 0x5741_4C31;
/// 固定头部字节数：magic4 + crc4 + seq8 + op1 + klen4 + vlen4 = 25。
pub const HEADER_LEN: usize = 25;
/// 单条 record 长度/上限兜底：长度字段来自不可信字节，先过闸再信任
/// （klen/vlen 是 u32，防恶意巨大长度打穿读取）。
pub const MAX_KEY: usize = 1 << 20;
pub const MAX_VALUE: usize = 1 << 20;

/// 操作类型：1=Put，2=Delete。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Op {
    Put,
    Delete,
}

impl Op {
    fn as_u8(self) -> u8 {
        match self {
            Op::Put => 1,
            Op::Delete => 2,
        }
    }

    fn from_u8(b: u8) -> Result<Self, WalError> {
        match b {
            1 => Ok(Op::Put),
            2 => Ok(Op::Delete),
            other => Err(WalError::UnknownOp(other)),
        }
    }
}

/// 一条已解析的 WAL record。`key`/`value` 借用自输入缓冲（零拷贝）。
#[derive(Debug, PartialEq, Eq)]
pub struct Record<'a> {
    pub sequence: u64,
    pub op: Op,
    pub key: &'a [u8],
    pub value: &'a [u8],
}

impl fmt::Display for Record<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.op {
            Op::Put => write!(
                f,
                "Put   seq={} key={} value={}",
                self.sequence,
                String::from_utf8_lossy(self.key),
                String::from_utf8_lossy(self.value)
            ),
            Op::Delete => write!(
                f,
                "Del   seq={} key={}",
                self.sequence,
                String::from_utf8_lossy(self.key)
            ),
        }
    }
}

/// 解析错误：与不可信输入斗争的四类失败。
#[derive(Debug, PartialEq, Eq)]
pub enum WalError {
    /// 魔数不对：可能错位或根本不是一个 WAL 文件。
    BadMagic(u32),
    /// 头部或 key/value 区不足：截断。
    Truncated,
    /// 校验失败：数据已损坏（声明值与实算值都保留，便于排障）。
    ChecksumMismatch { expected: u32, actual: u32 },
    /// op 不是 Put/Delete。
    UnknownOp(u8),
    /// key/value 长度超过上限（DoS 闸门）。
    TooLarge { what: &'static str, len: usize },
}

impl fmt::Display for WalError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            WalError::BadMagic(m) => write!(f, "魔数错误 0x{m:08X}（期望 \"WAL1\"）"),
            WalError::Truncated => write!(f, "数据截断：record 声明长度超过可用字节"),
            WalError::ChecksumMismatch { expected, actual } => {
                write!(
                    f,
                    "CRC 校验失败：声明 0x{expected:08X}，实算 0x{actual:08X}（数据已损坏）"
                )
            }
            WalError::UnknownOp(op) => write!(f, "未知操作码 {op}"),
            WalError::TooLarge { what, len } => write!(f, "{what} 长度 {len} 超过上限"),
        }
    }
}

impl Error for WalError {}

/// 从完整缓冲中解析**单条** record（缓冲须恰好以该 record 开头）。
///
/// 返回 `(Record, 占用字节数)`；占用数用于游标前进，支撑 [`records`] 的逐条迭代。
pub fn parse_record(buf: &[u8]) -> Result<(Record<'_>, usize), WalError> {
    let head = buf.get(..HEADER_LEN).ok_or(WalError::Truncated)?;
    // 安全纪律顺序：先魔数定位，再 CRC 验完整性，后取业务字段
    let magic = u32::from_le_bytes(head[0..4].try_into().map_err(|_| WalError::Truncated)?);
    if magic != MAGIC {
        return Err(WalError::BadMagic(magic));
    }
    let expected_crc = u32::from_le_bytes(head[4..8].try_into().map_err(|_| WalError::Truncated)?);
    let sequence = u64::from_le_bytes(head[8..16].try_into().map_err(|_| WalError::Truncated)?);
    let op = Op::from_u8(head[16])?;
    let klen =
        u32::from_le_bytes(head[17..21].try_into().map_err(|_| WalError::Truncated)?) as usize;
    let vlen =
        u32::from_le_bytes(head[21..25].try_into().map_err(|_| WalError::Truncated)?) as usize;
    if klen > MAX_KEY {
        return Err(WalError::TooLarge {
            what: "key",
            len: klen,
        });
    }
    if vlen > MAX_VALUE {
        return Err(WalError::TooLarge {
            what: "value",
            len: vlen,
        });
    }
    let key = buf
        .get(HEADER_LEN..HEADER_LEN + klen)
        .ok_or(WalError::Truncated)?;
    let value = buf
        .get(HEADER_LEN + klen..HEADER_LEN + klen + vlen)
        .ok_or(WalError::Truncated)?;
    let actual_crc = crc32_combine(key, value);
    if actual_crc != expected_crc {
        return Err(WalError::ChecksumMismatch {
            expected: expected_crc,
            actual: actual_crc,
        });
    }
    let total = HEADER_LEN + klen + vlen;
    Ok((
        Record {
            sequence,
            op,
            key,
            value,
        },
        total,
    ))
}

/// 对一段「多条 record 追加而成」的 WAL 缓冲做**惰性迭代**（零拷贝逐条借用）。
///
/// 语义：从头游走，每条成功返回 `Ok(record)`；遇错返回 `Err` 并**终止**迭代
/// （WAL 语义：损坏点之后的数据不可信，重放必须停在这里——这正是崩溃恢复要做的事，
/// 完整恢复机制属 ph25，本库只保证解析层把它显式暴露出来）。
pub fn records(buf: &[u8]) -> Records<'_> {
    Records { buf, pos: 0 }
}

/// [`records`] 返回的惰性迭代器。
pub struct Records<'a> {
    buf: &'a [u8],
    pos: usize,
}

impl<'a> Iterator for Records<'a> {
    type Item = Result<Record<'a>, WalError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.pos >= self.buf.len() {
            return None; // 干净结束
        }
        match parse_record(&self.buf[self.pos..]) {
            Ok((rec, used)) => {
                self.pos += used;
                Some(Ok(rec))
            }
            Err(e) => {
                // 出错的剩余部分不可再迭代：把游标推到底，保证后续 next() 返回 None
                self.pos = self.buf.len();
                Some(Err(e))
            }
        }
    }
}

/// 追加式 WAL 写入器：把结构化操作编码成字节流。与解析器严格镜像，供测试与演示使用。
#[derive(Debug, Default)]
pub struct WalWriter {
    buf: Vec<u8>,
}

impl WalWriter {
    pub fn new() -> Self {
        WalWriter::default()
    }

    /// 编码一条 record 并追加到日志尾。
    pub fn append(&mut self, sequence: u64, op: Op, key: &[u8], value: &[u8]) {
        let crc = crc32_combine(key, value);
        self.buf.extend_from_slice(&MAGIC.to_le_bytes());
        self.buf.extend_from_slice(&crc.to_le_bytes());
        self.buf.extend_from_slice(&sequence.to_le_bytes());
        self.buf.push(op.as_u8());
        self.buf
            .extend_from_slice(&(key.len() as u32).to_le_bytes());
        self.buf
            .extend_from_slice(&(value.len() as u32).to_le_bytes());
        self.buf.extend_from_slice(key);
        self.buf.extend_from_slice(value);
    }

    /// 取当前日志字节（借用）。
    pub fn as_bytes(&self) -> &[u8] {
        &self.buf
    }
}

// —— CRC32（IEEE 802.3，查表实现）——
// 工程上可换 crc32fast 等硬件加速库；零第三方演示查表写法。
const CRC_TABLE: [u32; 256] = make_crc_table();

const fn make_crc_table() -> [u32; 256] {
    let mut table = [0u32; 256];
    let mut i = 0usize;
    while i < 256 {
        let mut crc = i as u32;
        let mut k = 0;
        while k < 8 {
            crc = if crc & 1 == 1 {
                0xEDB8_8320 ^ (crc >> 1)
            } else {
                crc >> 1
            };
            k += 1;
        }
        table[i] = crc;
        i += 1;
    }
    table
}

/// 对 `key||value` 串联求 CRC32。
fn crc32_combine(key: &[u8], value: &[u8]) -> u32 {
    let mut crc = u32::MAX;
    for &b in key.iter().chain(value.iter()) {
        crc = CRC_TABLE[((crc ^ u32::from(b)) & 0xFF) as usize] ^ (crc >> 8);
    }
    crc ^ u32::MAX
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc_matches_ieee_test_vector() {
        // IEEE 802.3 标准向量：crc32("123456789") == 0xCBF43926
        assert_eq!(crc32_combine(b"123456789", b""), 0xCBF4_3926);
        assert_eq!(crc32_combine(b"", b""), 0);
    }

    #[test]
    fn put_record_roundtrip_zero_copy() {
        let mut w = WalWriter::new();
        w.append(1001, Op::Put, b"temperature", b"36.5");
        let bytes = w.as_bytes();
        let (rec, used) = parse_record(bytes).expect("合法 record");
        assert_eq!(used, bytes.len());
        assert_eq!(rec.sequence, 1001);
        assert_eq!(rec.op, Op::Put);
        assert_eq!(rec.key, b"temperature");
        assert_eq!(rec.value, b"36.5");
        // 零拷贝断言：key/value 直接借用输入缓冲内部
        let base = bytes.as_ptr() as usize;
        assert_eq!(rec.key.as_ptr() as usize - base, HEADER_LEN);
        assert_eq!(
            rec.value.as_ptr() as usize - base,
            HEADER_LEN + b"temperature".len()
        );
    }

    #[test]
    fn delete_record_has_empty_value() {
        let mut w = WalWriter::new();
        w.append(1002, Op::Delete, b"humidity", b"");
        let (rec, _) = parse_record(w.as_bytes()).expect("合法 record");
        assert_eq!(rec.op, Op::Delete);
        assert_eq!(rec.value, b"");
    }

    #[test]
    fn tampered_key_byte_fails_checksum() {
        let mut w = WalWriter::new();
        w.append(7, Op::Put, b"important", b"value");
        let mut bytes = w.as_bytes().to_vec();
        bytes[HEADER_LEN + 1] ^= 0x01; // 翻转 key 一个字节
        assert!(matches!(
            parse_record(&bytes),
            Err(WalError::ChecksumMismatch { .. })
        ));
    }

    #[test]
    fn bad_magic_and_unknown_op_are_err() {
        let mut w = WalWriter::new();
        w.append(1, Op::Put, b"k", b"v");
        let mut bad_magic = w.as_bytes().to_vec();
        bad_magic[0] = 0;
        assert!(matches!(
            parse_record(&bad_magic),
            Err(WalError::BadMagic(..))
        ));

        let mut bad_op = w.as_bytes().to_vec();
        bad_op[16] = 9;
        assert_eq!(parse_record(&bad_op).err(), Some(WalError::UnknownOp(9)));
    }

    #[test]
    fn truncated_record_is_err() {
        let mut w = WalWriter::new();
        w.append(1, Op::Put, b"key-that-is-long", b"value");
        let full = w.as_bytes();
        for cut in 0..full.len() {
            assert_eq!(parse_record(&full[..cut]).err(), Some(WalError::Truncated));
        }
    }

    #[test]
    fn records_iterator_yields_all_then_stops() {
        let mut w = WalWriter::new();
        w.append(1000, Op::Put, b"a", b"1");
        w.append(1001, Op::Delete, b"b", b"");
        w.append(1002, Op::Put, b"c", b"333");
        let parsed: Vec<_> = records(w.as_bytes())
            .collect::<Result<_, _>>()
            .expect("合法日志");
        assert_eq!(parsed.len(), 3);
        assert_eq!(parsed[0].sequence, 1000);
        assert_eq!(parsed[1].sequence, 1001);
        assert_eq!(parsed[2].key, b"c");
    }

    #[test]
    fn records_iterator_stops_at_corruption() {
        let mut w = WalWriter::new();
        w.append(1, Op::Put, b"one", b"1");
        w.append(2, Op::Put, b"two", b"22");
        w.append(3, Op::Put, b"three", b"333");
        let mut bytes = w.as_bytes().to_vec();
        // 损坏第二条的 key 首字节：第 2 条起点 = 第 1 条全长，其 key 区再隔一个 HEADER_LEN
        let first_len = HEADER_LEN + 3 + 1;
        bytes[first_len + HEADER_LEN] ^= 0xFF;
        let mut it = records(&bytes);
        assert!(it.next().expect("第一条").is_ok());
        assert!(matches!(
            it.next(),
            Some(Err(WalError::ChecksumMismatch { .. }))
        ));
        assert!(it.next().is_none(), "出错后迭代必须终止，不跳过继续");
    }
}

/// 断言宏与 panic 契约演示。单元测试放被测模块的**兄弟子模块**里，
/// `#[cfg(test)]` 让整段代码只参与 `cargo test` 编译，release 构建零残留。
#[cfg(test)]
mod assert_styles {
    // 用 `crate::` 绝对路径访问被测对象（区别于被测模块内的 `use super::*`，
    // 两种写法都常见；兄弟模块看不到父模块私有项，只能走 pub API）。
    use crate::{parse_record, Op, WalError, WalWriter};

    #[test]
    fn assert_eq_ne_sanity() {
        assert_eq!(1 + 1, 2); // 相等断言：值不相等则失败并打印两边表达式与值
        assert_ne!(2 + 2, 5); // 不等断言
    }

    #[test]
    fn matches_macro_matches_err_variant() {
        // 长度足（32 > 头部 25）但魔数全 0 → BadMagic；短输入则会是 Truncated
        let r = parse_record(&[0u8; 32]);
        // matches!：只关心「是不是这个变体」，不关心内部数据
        assert!(matches!(r, Err(WalError::BadMagic(_))));
    }

    #[test]
    fn result_returning_test_propagates() -> Result<(), WalError> {
        // 测试函数返回 Result：Err 时 `?` 传播，测试失败并打印 Display 错误
        let mut w = WalWriter::new();
        w.append(5, Op::Put, b"k", b"v");
        let (rec, used) = parse_record(w.as_bytes())?;
        assert_eq!(rec.sequence, 5);
        assert_eq!(used, w.as_bytes().len());
        Ok(())
    }

    #[test]
    #[should_panic(expected = "range start index 99 out of range")]
    #[allow(clippy::out_of_bounds_indexing)] // 故意越界：演示裸下标的 panic 契约
    fn naked_index_panics_on_short_buf() {
        // 复习 ph19 3.7 的安全纪律：裸下标越界直接 panic（这就是解析器一律用 get()
        // 的原因）；#[should_panic] 把「这个失败模式确实存在」变成可回归的契约测试
        let buf = b"short";
        let _ = &buf[99..];
    }

    #[test]
    #[ignore = "演示 #[ignore]：默认跳过、显式指定才跑（如慢速压力用例）"]
    fn ignored_long_running_case() {
        let mut w = WalWriter::new();
        for seq in 0..1_000u64 {
            w.append(seq, Op::Put, b"k", b"v");
        }
        let n = crate::records(w.as_bytes()).count();
        assert_eq!(n, 1_000);
    }
}
