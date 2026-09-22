//! 迷你 WAL record（教学简化，聚焦分配剖析）。
//!
//! 相对 ph19/ph20 的完整 WAL（magic+CRC+seq+op+key/value）此处**去掉 CRC 字段**，
//! 保留 layout 骨架：magic4 + seq8 + op1 + klen4 + vlen4 = 21B 头，后跟 key/value。
//! 字段一律小端。解析返回**借用输入**的 `Record<'a>`，迭代器逐条零拷贝游走——
//! 这正是「分配 ≈ 0」的对照基线；[`Records`] 出错即终止（WAL 重放语义）。

/// 魔数 `b"WAL1"`。
pub const MAGIC: u32 = 0x5741_4C31;
/// 固定头部字节数：magic4 + seq8 + op1 + klen4 + vlen4 = 21。
pub const HEADER_LEN: usize = 21;
/// 单条长度上限（不可信输入先过闸再信任）。
pub const MAX_KEY: usize = 1 << 20;
pub const MAX_VALUE: usize = 1 << 20;

/// 操作类型。
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

/// 一条已解析 record，key/value 借用输入缓冲。
#[derive(Debug, PartialEq, Eq)]
pub struct Record<'a> {
    pub sequence: u64,
    pub op: Op,
    pub key: &'a [u8],
    pub value: &'a [u8],
}

/// 解析错误。
#[derive(Debug, PartialEq, Eq)]
pub enum WalError {
    BadMagic(u32),
    Truncated,
    UnknownOp(u8),
    TooLarge { what: &'static str, len: usize },
}

/// 解析**单条** record（缓冲须以该 record 开头）。返回 `(Record, 占用字节数)`。
pub fn parse_record(buf: &[u8]) -> Result<(Record<'_>, usize), WalError> {
    let head = buf.get(..HEADER_LEN).ok_or(WalError::Truncated)?;
    let magic = u32::from_le_bytes(head[0..4].try_into().map_err(|_| WalError::Truncated)?);
    if magic != MAGIC {
        return Err(WalError::BadMagic(magic));
    }
    let sequence = u64::from_le_bytes(head[4..12].try_into().map_err(|_| WalError::Truncated)?);
    let op = Op::from_u8(head[12])?;
    let klen =
        u32::from_le_bytes(head[13..17].try_into().map_err(|_| WalError::Truncated)?) as usize;
    let vlen =
        u32::from_le_bytes(head[17..21].try_into().map_err(|_| WalError::Truncated)?) as usize;
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
    let used = HEADER_LEN + klen + vlen;
    Ok((
        Record {
            sequence,
            op,
            key,
            value,
        },
        used,
    ))
}

/// 对整段日志做惰性迭代，逐条借用。出错即终止（损坏点后不可信）。
pub fn records(buf: &[u8]) -> Records<'_> {
    Records { buf, pos: 0 }
}

/// [`records`] 返回的迭代器。
pub struct Records<'a> {
    buf: &'a [u8],
    pos: usize,
}

impl<'a> Iterator for Records<'a> {
    type Item = Result<Record<'a>, WalError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.pos >= self.buf.len() {
            return None;
        }
        match parse_record(&self.buf[self.pos..]) {
            Ok((rec, used)) => {
                self.pos += used;
                Some(Ok(rec))
            }
            Err(e) => {
                self.pos = self.buf.len();
                Some(Err(e))
            }
        }
    }
}

/// 追加式写入器：把操作编码成字节流，与解析器镜像。
#[derive(Debug, Default)]
pub struct WalWriter {
    buf: Vec<u8>,
}

impl WalWriter {
    pub fn new() -> Self {
        WalWriter::default()
    }

    pub fn append(&mut self, sequence: u64, op: Op, key: &[u8], value: &[u8]) {
        self.buf.extend_from_slice(&MAGIC.to_le_bytes());
        self.buf.extend_from_slice(&sequence.to_le_bytes());
        self.buf.push(op.as_u8());
        self.buf
            .extend_from_slice(&(key.len() as u32).to_le_bytes());
        self.buf
            .extend_from_slice(&(value.len() as u32).to_le_bytes());
        self.buf.extend_from_slice(key);
        self.buf.extend_from_slice(value);
    }

    pub fn as_bytes(&self) -> &[u8] {
        &self.buf
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_zero_copy() {
        let mut w = WalWriter::new();
        w.append(42, Op::Put, b"temperature", b"36.5");
        let bytes = w.as_bytes();
        let (rec, used) = parse_record(bytes).expect("合法 record");
        assert_eq!(used, bytes.len());
        assert_eq!(rec.sequence, 42);
        assert_eq!(rec.op, Op::Put);
        assert_eq!(rec.key, &b"temperature"[..]);
        assert_eq!(rec.value, &b"36.5"[..]);
        let base = bytes.as_ptr() as usize;
        assert_eq!(rec.key.as_ptr() as usize - base, HEADER_LEN);
    }

    #[test]
    fn iterator_stops_at_corruption() {
        let mut w = WalWriter::new();
        w.append(1, Op::Put, b"one", b"1");
        w.append(2, Op::Put, b"two", b"22");
        let mut bytes = w.as_bytes().to_vec();
        // 教学简化去掉了 CRC，损坏 value 无法被发现；这里损坏第 1 条的 op 字节
        // （偏移 12），让 op 解码失败 → 迭代在错误处终止、不跳过继续
        bytes[12] ^= 0xFF;
        let mut it = records(&bytes);
        assert!(it.next().is_some());
        assert!(it.next().is_none(), "出错后必须终止");
    }
}
