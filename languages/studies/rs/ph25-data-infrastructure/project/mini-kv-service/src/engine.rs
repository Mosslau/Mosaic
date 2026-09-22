//! 存储引擎：WAL（磁盘）+ MemTable（内存有序表），迷你 LSM 的最小持久化形态。
//!
//! 写路径：`put/delete` 先 append record 到 WAL 并 fsync，再改内存表——崩溃后
//! 从 WAL 重放即可恢复（ex01/sol-01 的引擎层纪律在本服务里作为持久化底座）。
//! 读路径：`get` 查内存表、`scan` 在有序表上闭区间扫描。
//! 本工程不实现多级 SSTable 与后台 compaction——它们是 examples/ex02~ex03 与
//! exercises/sol-02~sol-03 演示过的组件，本收官工程把「WAL + 有序内存表」做成
//! 一个可以被 HTTP 与 Agent 工具层稳定调用的最小持久化 KV。

use std::collections::BTreeMap;
use std::fmt;
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::Path;

const MAGIC: u32 = 0x5741_4C4B; // "WALK"
const HEADER_LEN: usize = 13; // magic4 + type1 + klen4 + vlen4
const MAX_KEY: usize = 1 << 20;
const MAX_VALUE: usize = 1 << 20;

#[derive(Debug)]
pub enum EngError {
    BadMagic { got: u32 },
    TooLarge { what: &'static str, len: usize },
    UnknownOp(u8),
    Io(std::io::Error),
}

impl fmt::Display for EngError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EngError::BadMagic { got } => write!(f, "WAL 魔数错误 0x{got:08X}"),
            EngError::TooLarge { what, len } => write!(f, "{what} 长度 {len} 超上限"),
            EngError::UnknownOp(op) => write!(f, "WAL 未知操作码 {op}"),
            EngError::Io(e) => write!(f, "I/O：{e}"),
        }
    }
}
impl std::error::Error for EngError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            EngError::Io(e) => Some(e),
            _ => None,
        }
    }
}
impl From<std::io::Error> for EngError {
    fn from(e: std::io::Error) -> Self {
        EngError::Io(e)
    }
}

const CRC_TABLE: [u32; 256] = make_table();
const fn make_table() -> [u32; 256] {
    let mut t = [0u32; 256];
    let mut i = 0usize;
    while i < 256 {
        let mut c = i as u32;
        let mut k = 0;
        while k < 8 {
            c = if c & 1 == 1 {
                0xEDB8_8320 ^ (c >> 1)
            } else {
                c >> 1
            };
            k += 1;
        }
        t[i] = c;
        i += 1;
    }
    t
}
fn crc32(data: &[u8]) -> u32 {
    let mut c = u32::MAX;
    for &b in data {
        c = CRC_TABLE[((c ^ u32::from(b)) & 0xFF) as usize] ^ (c >> 8);
    }
    c ^ u32::MAX
}
fn be32(b: &[u8]) -> u32 {
    u32::from_be_bytes([b[0], b[1], b[2], b[3]])
}
fn put_be32(buf: &mut Vec<u8>, v: u32) {
    buf.extend_from_slice(&v.to_be_bytes());
}

/// 有序内存表 + WAL 的持久化 KV。
pub struct Engine {
    file: File,
    mem: BTreeMap<Vec<u8>, Vec<u8>>,
    /// open 时是否发生了残尾截断（恢复日志位点）。
    pub torn_recovered: bool,
    /// 本次会话执行过的写操作数（统计/日志用）。
    pub ops: u64,
}

impl Engine {
    /// 打开（或新建）引擎：重放 WAL 重建内存表；残尾自动截断修复。
    pub fn open(dir: impl AsRef<Path>) -> Result<Engine, EngError> {
        let dir = dir.as_ref();
        std::fs::create_dir_all(dir)?;
        let path = dir.join("engine.wal");
        let mut file = OpenOptions::new()
            .create(true)
            .read(true)
            .write(true)
            .open(&path)?;
        let mut mem = BTreeMap::new();
        let mut buf = Vec::new();
        file.read_to_end(&mut buf)?;
        let clean_end = replay(&buf, &mut mem)?;
        let torn_recovered = (clean_end as usize) < buf.len();
        if torn_recovered {
            file.set_len(clean_end)?;
            file.sync_all()?;
        }
        file.seek(SeekFrom::End(0))?; // 写游标放回文件尾（截断后原游标可能在 EOF 外）
        Ok(Engine {
            file,
            mem,
            torn_recovered,
            ops: 0,
        })
    }

    /// 追加一条记录并落盘（fsync）再改内存表。**append 返回 ≠ 持久化**：sync 才算。
    fn write_op(&mut self, op: u8, key: &[u8], value: &[u8]) -> Result<(), EngError> {
        if key.len() > MAX_KEY {
            return Err(EngError::TooLarge {
                what: "key",
                len: key.len(),
            });
        }
        if value.len() > MAX_VALUE {
            return Err(EngError::TooLarge {
                what: "value",
                len: value.len(),
            });
        }
        let mut buf = Vec::with_capacity(HEADER_LEN + key.len() + value.len() + 4);
        put_be32(&mut buf, MAGIC);
        buf.push(op);
        put_be32(&mut buf, key.len() as u32);
        put_be32(&mut buf, value.len() as u32);
        buf.extend_from_slice(key);
        buf.extend_from_slice(value);
        let crc = crc32(&buf[4..]); // CRC 覆盖 type..value
        put_be32(&mut buf, crc);
        self.file.write_all(&buf)?;
        self.file.sync_all()?;
        Ok(())
    }

    pub fn put(&mut self, key: &[u8], value: &[u8]) -> Result<(), EngError> {
        self.write_op(1, key, value)?;
        self.mem.insert(key.to_vec(), value.to_vec());
        self.ops += 1;
        Ok(())
    }

    pub fn delete(&mut self, key: &[u8]) -> Result<(), EngError> {
        self.write_op(2, key, &[])?;
        self.mem.remove(key);
        self.ops += 1;
        Ok(())
    }

    pub fn get(&self, key: &[u8]) -> Option<&[u8]> {
        self.mem.get(key).map(Vec::as_slice)
    }

    /// 闭区间 range scan：返回 `[start, end]` 内有序列出的 (key, value)。
    /// start > end（如 start="z" end="a"）是空区间，返回空而非 panic。
    pub fn scan(&self, start: &[u8], end: &[u8]) -> Vec<(Vec<u8>, Vec<u8>)> {
        if start > end {
            return Vec::new();
        }
        self.mem
            .range(start.to_vec()..=end.to_vec())
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect()
    }

    pub fn len(&self) -> usize {
        self.mem.len()
    }

    pub fn is_empty(&self) -> bool {
        self.mem.is_empty()
    }
}

/// 重放 WAL 到内存表，返回最后一个完整 record 之后的偏移。
fn replay(buf: &[u8], mem: &mut BTreeMap<Vec<u8>, Vec<u8>>) -> Result<u64, EngError> {
    let mut pos = 0usize;
    while buf.len() - pos >= HEADER_LEN {
        let head = &buf[pos..pos + HEADER_LEN];
        if be32(&head[0..4]) != MAGIC {
            return Ok(pos as u64);
        }
        let op = match head[4] {
            1 => 1u8,
            2 => 2u8,
            other => return Err(EngError::UnknownOp(other)),
        };
        let klen = be32(&head[5..9]) as usize;
        let vlen = be32(&head[9..13]) as usize;
        if klen > MAX_KEY || vlen > MAX_VALUE {
            return Err(EngError::TooLarge {
                what: "k/v",
                len: klen.max(vlen),
            });
        }
        let record_end = pos + HEADER_LEN + klen + vlen;
        if buf.len() - pos < HEADER_LEN + klen + vlen + 4 {
            return Ok(pos as u64); // 残尾
        }
        let expect = be32(&buf[record_end..record_end + 4]);
        if crc32(&buf[pos + 4..record_end]) != expect {
            return Ok(pos as u64); // 损坏/残写：停在这里
        }
        let key = &buf[pos + HEADER_LEN..pos + HEADER_LEN + klen];
        let value = &buf[pos + HEADER_LEN + klen..record_end];
        if op == 1 {
            mem.insert(key.to_vec(), value.to_vec());
        } else {
            mem.remove(key);
        }
        pos = record_end + 4;
    }
    Ok(pos as u64)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmpdir(name: &str) -> std::path::PathBuf {
        let d =
            std::env::temp_dir().join(format!("ph25-project-eng-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        d
    }

    #[test]
    fn reopen_restores_state() {
        let dir = tmpdir("reopen");
        {
            let mut e = Engine::open(&dir).unwrap();
            e.put(b"a", b"1").unwrap();
            e.put(b"b", b"2").unwrap();
            e.delete(b"a").unwrap();
        }
        let e = Engine::open(&dir).unwrap();
        assert_eq!(e.get(b"a"), None);
        assert_eq!(e.get(b"b"), Some(&b"2"[..]));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn torn_tail_auto_truncated() {
        let dir = tmpdir("torn");
        {
            let mut e = Engine::open(&dir).unwrap();
            e.put(b"k", b"v").unwrap();
            drop(e);
            let mut f = OpenOptions::new()
                .append(true)
                .open(dir.join("engine.wal"))
                .unwrap();
            f.write_all(&[0x57, 0x41, 0x4C, 0x4B, 0x01]).unwrap();
        }
        let e = Engine::open(&dir).unwrap();
        assert!(e.torn_recovered);
        assert_eq!(e.get(b"k"), Some(&b"v"[..]));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn scan_returns_sorted_closed_range() {
        let dir = tmpdir("scan");
        let mut e = Engine::open(&dir).unwrap();
        for (k, v) in [("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")] {
            e.put(k.as_bytes(), v.as_bytes()).unwrap();
        }
        let rows = e.scan(b"b", b"c");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].0, b"b");
        assert_eq!(rows[1].0, b"c");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
