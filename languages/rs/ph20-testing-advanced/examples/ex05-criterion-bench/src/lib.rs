//! examples/ex05：criterion 基准测试的被测对象（DUT）。
//!
//! 复刻自 ph19 阶段项目 `wal-record-parser` 的迷你 WAL record 解析器
//! （格式见 ph19 主文档 3.8，字段一律小端）。本 crate 的**基准**在 `benches/`：
//! 对比两条解析路径——零拷贝借用（records 返回 &[u8]）vs 逐条复制成拥有数据
//! （模拟「落地到 MemTable 需要拥有 key/value」的真实代价）。本 lib 保持纯净，
//! 只暴露解析 API；两种「对比实现」都在 bench 文件里用黑盒（black_box）包起来。
//!
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
