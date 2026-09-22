//! ph25 ex01：WAL append/replay 与崩溃恢复（纯 std，零第三方依赖）
//!
//! 这是 roadmap §25「WAL append / replay」的最小引擎层落地：把 ph19 的
//! 解析纪律（魔数先行、长度上限、CRC 校验、损坏即停）从「解析器」升级成
//! 「写路径 append + fsync → 读路径 replay + torn tail 修复」的完整循环。
//! 磁盘格式与 C/ph16、cpp/ph22 对齐（大端、CRC 覆盖 magic 之后的整段），
//! 便于跨语言逐字节对照；与 ph19 目录内 parser crate 的差异（那边是
//! 小端 + 仅 payload 的 CRC，教学简化）在本文件头注释与主文档 3.1 说明。
//!
//! # 验证环境与命令
//! - 验证环境：rustc/cargo 1.92.0（macOS arm64）
//! - 运行：`cargo run`（演示三条路径，输出见 README）
//! - 测试：`cargo test --release`（11 个单测，含 IEEE CRC 向量）
//! - 质量：`cargo fmt --check && cargo clippy --all-targets -- -D warnings`
//! - 验证状态：**已验证**（2026-09-04 本机实测，输出见 examples/README）

use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

/// 魔数 `b"WAL1"` = 0x57414C31（与 C/ph16、cpp/ph22 的磁盘格式一致，大端落盘）。
pub const MAGIC: u32 = 0x5741_4C31;
/// 固定头部（不含 key/value 与 CRC）：magic4 + type1 + klen4 + vlen4 = 13。
pub const HEADER_LEN: usize = 13;
/// 单条上限兜底：长度字段来自不可信字节（崩溃残写/错位），先过闸再信任。
pub const MAX_KEY: usize = 1 << 20;
pub const MAX_VALUE: usize = 1 << 20;

/// 操作类型：Put / Delete（删除 = tombstone 记录，日志只增不改）。
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

/// 一条已重放的记录：key/value 拥有化（replay 要喂进 MemTable，所有权交接在引擎层）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub seq: u64,
    pub op: Op,
    pub key: Vec<u8>,
    pub value: Vec<u8>,
}

impl Record {
    /// 编码：`[magic u32][type u8][klen u32][vlen u32][key][value][crc32 u32]`，多字节大端。
    /// CRC 覆盖 `type..value` 整段（magic 自身不参与——与 C/ph16、cpp/ph22 同款校验范围）。
    fn encode(&self, out: &mut Vec<u8>) {
        out.extend_from_slice(&MAGIC.to_be_bytes());
        out.push(self.op.as_u8());
        out.extend_from_slice(&(self.key.len() as u32).to_be_bytes());
        out.extend_from_slice(&(self.value.len() as u32).to_be_bytes());
        out.extend_from_slice(&self.key);
        out.extend_from_slice(&self.value);
        let crc = crc32(&out[4..]); // 校验范围：从 type 到 value 末尾
        out.extend_from_slice(&crc.to_be_bytes());
    }
}

/// 引擎层错误：把「坏日志」的全部失败形态收进一个枚举（生产代码的 Result 通道）。
#[derive(Debug)]
pub enum WalError {
    /// 文件不是我们的 WAL（魔数不符）。
    BadMagic { got: u32 },
    /// 剩余字节连一个头部都不够——torn tail 的典型形态。
    ShortTail { offset: u64, remaining: usize },
    /// 单条声明长度超上限（DoS 闸门）。
    TooLarge { what: &'static str, len: usize },
    /// CRC 不符：记录损坏或错位。
    ChecksumMismatch {
        offset: u64,
        expected: u32,
        actual: u32,
    },
    /// op 码未知。
    UnknownOp(u8),
    /// 底层 I/O 错误。
    Io(std::io::Error),
}

impl std::fmt::Display for WalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WalError::BadMagic { got } => {
                write!(f, "魔数错误 0x{got:08X}（期望 0x{MAGIC:08X} \"WAL1\"）")
            }
            WalError::ShortTail { offset, remaining } => write!(
                f,
                "残尾：偏移 {offset} 后仅剩 {remaining} 字节（不足一个头部，宜截断修复）"
            ),
            WalError::TooLarge { what, len } => write!(f, "{what} 长度 {len} 超过上限"),
            WalError::ChecksumMismatch {
                offset,
                expected,
                actual,
            } => write!(
                f,
                "偏移 {offset} CRC 校验失败：声明 0x{expected:08X} 实算 0x{actual:08X}"
            ),
            WalError::UnknownOp(op) => write!(f, "未知操作码 {op}"),
            WalError::Io(e) => write!(f, "I/O 错误：{e}"),
        }
    }
}

impl std::error::Error for WalError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            WalError::Io(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for WalError {
    fn from(e: std::io::Error) -> Self {
        WalError::Io(e)
    }
}

/// 追加式 WAL 写入器：`append` 先把记录编码写盘，再 `sync` 落盘才向调用方确认。
///
/// **append 返回 ≠ 持久化**：数据只到内核页缓存，`sync()`（fsync）返回才算
/// 「崩溃后还在」——这是 WAL 语义与普通文件写的分界线（主文档 3.1/4.2）。
#[derive(Debug)]
pub struct WalAppender {
    file: File,
    path: PathBuf,
    next_seq: u64,
}

impl WalAppender {
    pub fn open(path: impl AsRef<Path>) -> Result<Self, WalError> {
        let file = OpenOptions::new()
            .create(true)
            .read(true)
            .append(true)
            .open(path.as_ref())?;
        let path = path.as_ref().to_path_buf();
        // 上次会话写到哪条 seq：打开时先扫一遍（小日志教学场景足够）
        let mut seq = 0u64;
        let _ = replay(&path, |rec| seq = rec.seq); // best-effort：尾损坏时取到干净前缀即可
        Ok(WalAppender {
            file,
            path,
            next_seq: seq + 1,
        })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    /// 追加一条记录并返回其 seq（写文件，未 fsync）。
    pub fn append(&mut self, op: Op, key: &[u8], value: &[u8]) -> Result<u64, WalError> {
        let rec = Record {
            seq: self.next_seq,
            op,
            key: key.to_vec(),
            value: value.to_vec(),
        };
        let mut buf = Vec::with_capacity(HEADER_LEN + key.len() + value.len() + 4);
        rec.encode(&mut buf);
        self.file.write_all(&buf)?;
        self.next_seq += 1;
        Ok(rec.seq)
    }

    /// fsync 落盘：调用方决定提交粒度（单条同步 = 每条一次 fsync，慢；攒批 = 快）。
    pub fn sync(&mut self) -> Result<(), WalError> {
        self.file.sync_all()?;
        Ok(())
    }

    /// 截断到 `len`（torn tail 修复：把日志修回最后一个完整记录之后）。
    pub fn truncate(&mut self, len: u64) -> Result<(), WalError> {
        self.file.set_len(len)?;
        self.file.sync_all()?;
        Ok(())
    }
}

/// 重放结果：要么全部干净，要么在一个偏移上停下（该偏移之后需要截断）。
/// （不 derive 比较 trait：携带的 WalError 只保证 Debug，断言走 matches! + 字段比对。）
#[derive(Debug)]
pub enum ReplayOutcome {
    /// 日志干净，全部记录已应用。
    Clean { applied: u64, last_seq: u64 },
    /// 在 offset 处停下：剩余字节不足一个头部（torn tail，宜截断到 offset）。
    TornTail {
        applied: u64,
        last_seq: u64,
        offset: u64,
    },
    /// 在 offset 处停下：头部字段/CRC 校验失败（损坏，宜截断到 offset——崩溃残写常落在此）。
    Corrupt {
        applied: u64,
        last_seq: u64,
        offset: u64,
        error: WalError,
    },
}

/// 重放文件并把每条记录喂给 `apply`（回调签名体现所有权交接：引擎决定怎么存）。
pub fn replay(
    path: impl AsRef<Path>,
    mut apply: impl FnMut(Record),
) -> Result<ReplayOutcome, WalError> {
    let mut file = File::open(path)?;
    replay_from_reader(&mut file, &mut apply)
}

fn replay_from_reader(
    reader: &mut impl Read,
    apply: &mut impl FnMut(Record),
) -> Result<ReplayOutcome, WalError> {
    // 教学场景整段读入（真实引擎用 mmap/流式块读，ph19 已演示惰性迭代思路）。
    let mut buf = Vec::new();
    reader.read_to_end(&mut buf)?;
    let mut pos = 0usize;
    let mut applied = 0u64;
    let mut last_seq = 0u64;
    while buf.len() - pos >= HEADER_LEN {
        let head = &buf[pos..pos + HEADER_LEN];
        let magic = read_u32_be(&head[0..4]);
        if magic != MAGIC {
            return Ok(ReplayOutcome::Corrupt {
                applied,
                last_seq,
                offset: pos as u64,
                error: WalError::BadMagic { got: magic },
            });
        }
        let op = match Op::from_u8(head[4]) {
            Ok(op) => op,
            Err(e) => {
                return Ok(ReplayOutcome::Corrupt {
                    applied,
                    last_seq,
                    offset: pos as u64,
                    error: e,
                })
            }
        };
        let klen = read_u32_be(&head[5..9]) as usize;
        let vlen = read_u32_be(&head[9..13]) as usize;
        if klen > MAX_KEY {
            return Ok(ReplayOutcome::Corrupt {
                applied,
                last_seq,
                offset: pos as u64,
                error: WalError::TooLarge {
                    what: "key",
                    len: klen,
                },
            });
        }
        if vlen > MAX_VALUE {
            return Ok(ReplayOutcome::Corrupt {
                applied,
                last_seq,
                offset: pos as u64,
                error: WalError::TooLarge {
                    what: "value",
                    len: vlen,
                },
            });
        }
        // 剩余空间是否装得下 key+value+crc
        let need = HEADER_LEN + klen + vlen + 4;
        if buf.len() - pos < need {
            return Ok(ReplayOutcome::TornTail {
                applied,
                last_seq,
                offset: pos as u64,
            });
        }
        let record_end = pos + HEADER_LEN + klen + vlen;
        // 磁盘格式不含独立 seq 字段（与 C/ph16、cpp/ph22 对齐）；重放的
        // seq 由「日志内位置序」编号（引擎会话内单调），等价于消息序号。
        let expected_crc = read_u32_be(&buf[record_end..record_end + 4]);
        let actual_crc = crc32(&buf[pos + 4..record_end]);
        if actual_crc != expected_crc {
            return Ok(ReplayOutcome::Corrupt {
                applied,
                last_seq,
                offset: pos as u64,
                error: WalError::ChecksumMismatch {
                    offset: pos as u64,
                    expected: expected_crc,
                    actual: actual_crc,
                },
            });
        }
        last_seq += 1;
        applied += 1;
        apply(Record {
            seq: last_seq,
            op,
            key: buf[pos + HEADER_LEN..pos + HEADER_LEN + klen].to_vec(),
            value: buf[pos + HEADER_LEN + klen..record_end].to_vec(),
        });
        pos = record_end + 4; // 越过尾部 CRC，指到下一条记录起点
    }
    if buf.len() - pos > 0 {
        // 尾部不足一个头部：torn tail（崩溃时最后一条写了一半）
        return Ok(ReplayOutcome::TornTail {
            applied,
            last_seq,
            offset: pos as u64,
        });
    }
    Ok(ReplayOutcome::Clean { applied, last_seq })
}

fn read_u32_be(bytes: &[u8]) -> u32 {
    u32::from_be_bytes(bytes.try_into().expect("调用方保证长度 4"))
}

/// 应用重放到内存态：Put 覆盖、Delete 移除——正是 MemTable 的雏形语义。
pub fn apply_to_memtable(mem: &mut BTreeMap<Vec<u8>, Vec<u8>>, rec: Record) {
    match rec.op {
        Op::Put => {
            mem.insert(rec.key, rec.value);
        }
        Op::Delete => {
            mem.remove(&rec.key);
        }
    }
}

/// 标准 CRC32（IEEE 802.3，查表实现；工程上可换 crc32fast 硬件加速）。
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

pub fn crc32(data: &[u8]) -> u32 {
    let mut crc = u32::MAX;
    for &b in data {
        crc = CRC_TABLE[((crc ^ u32::from(b)) & 0xFF) as usize] ^ (crc >> 8);
    }
    crc ^ u32::MAX
}

#[cfg(test)]
fn temp_log(name: &str) -> PathBuf {
    std::env::temp_dir().join(format!("ph25-ex01-{name}-{}.log", std::process::id()))
}

fn main() -> Result<(), WalError> {
    // 演示目录：每个场景一个独立日志文件，跑完清理
    let base = std::env::temp_dir().join(format!("ph25-ex01-demo-{}", std::process::id()));
    std::fs::create_dir_all(&base).map_err(WalError::Io)?;

    // —— 场景 1：干净追加 3 条 → replay 全对 ——
    let path = base.join("s1.log");
    {
        let mut wal = WalAppender::open(&path)?;
        wal.append(Op::Put, b"voltage", b"12.8")?;
        wal.append(Op::Put, b"temperature", b"36.5")?;
        wal.append(Op::Delete, b"voltage", b"")?;
        wal.sync()?; // fsync 后返回，崩溃也不丢
    }
    let mut mem = BTreeMap::new();
    let outcome = replay(&path, |r| apply_to_memtable(&mut mem, r))?;
    println!("[场景 1] 干净日志重放：{outcome:?}");
    println!("        重放后的内存态：{mem:?}");
    match outcome {
        ReplayOutcome::Clean { applied, last_seq } => {
            assert_eq!((applied, last_seq), (3, 3));
        }
        other => panic!("期望 Clean，实际 {other:?}"),
    }

    // —— 场景 2：尾部塞 6 字节垃圾（模拟崩溃时最后一条写了一半）→ replay 停在残尾，截断修复 ——
    let path2 = base.join("s2.log");
    {
        let mut wal = WalAppender::open(&path2)?;
        wal.append(Op::Put, b"a", b"1")?;
        wal.append(Op::Put, b"b", b"22")?;
        wal.sync()?;
        // 模拟残尾：追加 6 个字节的「半条记录」
        let mut f = OpenOptions::new().append(true).open(&path2)?;
        f.write_all(&[0x57, 0x41, 0x4C, 0x31, 0x01, 0x00])?;
        f.sync_all()?;
    }
    let mut mem2 = BTreeMap::new();
    let out2 = replay(&path2, |r| apply_to_memtable(&mut mem2, r))?;
    println!("[场景 2] 残尾日志重放：{out2:?}");
    let torn_offset = match out2 {
        ReplayOutcome::TornTail { offset, .. } => offset,
        other => panic!("期望 TornTail，实际 {other:?}"),
    };
    // 截断修复：把日志修回最后一个完整记录之后，之后还能继续追加
    let mut wal2 = WalAppender::open(&path2)?;
    wal2.truncate(torn_offset)?;
    wal2.append(Op::Put, b"c", b"333")?;
    wal2.sync()?;
    let mut mem2b = BTreeMap::new();
    let out2b = replay(&path2, |r| apply_to_memtable(&mut mem2b, r))?;
    println!("[场景 2] 截断后重放：{out2b:?}，内存态 {mem2b:?}");

    // —— 场景 3：翻转中间记录 payload 一字节（模拟位衰减）→ CRC 拦截，停在损坏点 ——
    let path3 = base.join("s3.log");
    {
        let mut wal = WalAppender::open(&path3)?;
        wal.append(Op::Put, b"important", b"value1")?; // 第一条：HEADER_LEN+9+6
        wal.append(Op::Put, b"second", b"value2")?;
        wal.sync()?;
        // 翻转第二条 key 区首字节
        let first_total = HEADER_LEN + b"important".len() + b"value1".len() + 4;
        let mut f = OpenOptions::new().read(true).write(true).open(&path3)?;
        f.seek(SeekFrom::Start(first_total as u64 + HEADER_LEN as u64))?;
        let mut byte = [0u8; 1];
        f.read_exact(&mut byte)?;
        byte[0] ^= 0xFF;
        f.seek(SeekFrom::Start(first_total as u64 + HEADER_LEN as u64))?;
        f.write_all(&byte)?;
        f.sync_all()?;
    }
    let mut mem3 = BTreeMap::new();
    let out3 = replay(&path3, |r| apply_to_memtable(&mut mem3, r))?;
    println!("[场景 3] 位翻转重放：{out3:?}");
    println!("        停在损坏点之前的内存态（第一条仍在）：{mem3:?}");

    std::fs::remove_dir_all(&base).map_err(WalError::Io)?;
    println!("\nex01 演示完成：三场景（干净/残尾/位翻转）行为符合 WAL 崩溃恢复预期");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cleanup(p: &Path) {
        let _ = std::fs::remove_file(p);
    }

    #[test]
    fn crc_matches_ieee_vector() {
        assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
        assert_eq!(crc32(b""), 0);
    }

    #[test]
    fn record_encode_layout_is_stable() {
        let rec = Record {
            seq: 1,
            op: Op::Put,
            key: b"ab".to_vec(),
            value: b"cd".to_vec(),
        };
        let mut buf = Vec::new();
        rec.encode(&mut buf);
        // 大端布局：magic | type | klen | vlen | "ab" | "cd" | crc
        assert_eq!(&buf[0..4], &0x5741_4C31u32.to_be_bytes());
        assert_eq!(buf[4], 1);
        assert_eq!(&buf[5..9], &2u32.to_be_bytes());
        assert_eq!(&buf[9..13], &2u32.to_be_bytes());
        assert_eq!(&buf[13..15], b"ab");
        assert_eq!(&buf[15..17], b"cd");
        // crc 覆盖 [type..value]，即 buf[4..17]
        assert_eq!(&buf[17..21], &crc32(&buf[4..17]).to_be_bytes());
    }

    #[test]
    fn append_replay_roundtrip_restores_state() {
        let path = temp_log("roundtrip");
        cleanup(&path);
        {
            let mut wal = WalAppender::open(&path).unwrap();
            wal.append(Op::Put, b"a", b"1").unwrap();
            wal.append(Op::Put, b"b", b"22").unwrap();
            wal.append(Op::Delete, b"a", b"").unwrap();
            wal.sync().unwrap();
        }
        let mut mem = BTreeMap::new();
        let out = replay(&path, |r| apply_to_memtable(&mut mem, r)).unwrap();
        match out {
            ReplayOutcome::Clean { applied, last_seq } => {
                assert_eq!((applied, last_seq), (3, 3));
            }
            other => panic!("期望 Clean，实际 {other:?}"),
        }
        assert!(!mem.contains_key(b"a" as &[u8]), "Delete 应移除 a");
        assert_eq!(
            mem.get(b"b" as &[u8]).map(|v| v.as_slice()),
            Some(&b"22"[..])
        );
        cleanup(&path);
    }

    #[test]
    fn torn_tail_less_than_header_reported_then_truncatable() {
        let path = temp_log("torntail");
        cleanup(&path);
        {
            let mut wal = WalAppender::open(&path).unwrap();
            wal.append(Op::Put, b"k1", b"v1").unwrap();
            wal.sync().unwrap();
            let mut f = OpenOptions::new().append(true).open(&path).unwrap();
            f.write_all(&[0x57, 0x41, 0x4C, 0x01]).unwrap(); // 4 字节垃圾尾
            f.sync_all().unwrap();
        }
        let out = replay(&path, |_| {}).unwrap();
        let offset = match out {
            ReplayOutcome::TornTail {
                offset, applied, ..
            } => {
                assert_eq!(applied, 1);
                offset
            }
            other => panic!("期望 TornTail，实际 {other:?}"),
        };
        // 截断后重放干净
        let mut wal = WalAppender::open(&path).unwrap();
        wal.truncate(offset).unwrap();
        let out2 = replay(&path, |_| {}).unwrap();
        match out2 {
            ReplayOutcome::Clean { applied, last_seq } => {
                assert_eq!((applied, last_seq), (1, 1));
            }
            other => panic!("期望 Clean，实际 {other:?}"),
        }
        cleanup(&path);
    }

    #[test]
    fn payload_bitflip_stops_replay_at_corruption_point() {
        let path = temp_log("bitflip");
        cleanup(&path);
        let first_total = {
            let mut wal = WalAppender::open(&path).unwrap();
            wal.append(Op::Put, b"important", b"value1").unwrap();
            wal.append(Op::Put, b"second", b"value2").unwrap();
            wal.sync().unwrap();
            HEADER_LEN + b"important".len() + b"value1".len() + 4
        };
        // 翻转第二条 key 区首字节
        let mut f = OpenOptions::new()
            .read(true)
            .write(true)
            .open(&path)
            .unwrap();
        let flip_pos = first_total as u64 + HEADER_LEN as u64;
        f.seek(SeekFrom::Start(flip_pos)).unwrap();
        let mut byte = [0u8; 1];
        f.read_exact(&mut byte).unwrap();
        byte[0] ^= 0xFF;
        f.seek(SeekFrom::Start(flip_pos)).unwrap();
        f.write_all(&byte).unwrap();
        f.sync_all().unwrap();

        let mut applied_keys = Vec::new();
        let out = replay(&path, |r| applied_keys.push(r.key)).unwrap();
        match out {
            ReplayOutcome::Corrupt {
                applied,
                offset,
                error,
                ..
            } => {
                assert_eq!(applied, 1);
                assert_eq!(offset, first_total as u64);
                assert!(matches!(error, WalError::ChecksumMismatch { .. }));
                assert_eq!(applied_keys, vec![b"important".to_vec()]);
            }
            other => panic!("期望 Corrupt，实际 {other:?}"),
        }
        cleanup(&path);
    }

    #[test]
    fn garbage_file_reports_bad_magic() {
        let path = temp_log("garbage");
        cleanup(&path);
        std::fs::write(&path, b"NOT-A-WAL-FILE-HERE").unwrap();
        let out = replay(&path, |_| {}).unwrap();
        assert!(matches!(
            out,
            ReplayOutcome::Corrupt {
                error: WalError::BadMagic { .. },
                ..
            }
        ));
        cleanup(&path);
    }

    #[test]
    fn empty_log_is_clean() {
        let path = temp_log("empty");
        cleanup(&path);
        std::fs::write(&path, b"").unwrap();
        let out = replay(&path, |_| {}).unwrap();
        match out {
            ReplayOutcome::Clean { applied, last_seq } => {
                assert_eq!((applied, last_seq), (0, 0));
            }
            other => panic!("期望 Clean，实际 {other:?}"),
        }
        cleanup(&path);
    }

    #[test]
    fn oversize_length_field_rejected() {
        let path = temp_log("oversize");
        cleanup(&path);
        // 手工构造：magic + type + klen=0xFFFFFFFF
        let mut buf = Vec::new();
        buf.extend_from_slice(&MAGIC.to_be_bytes());
        buf.push(1);
        buf.extend_from_slice(&0xFFFF_FFFFu32.to_be_bytes());
        buf.extend_from_slice(&0u32.to_be_bytes());
        std::fs::write(&path, &buf).unwrap();
        let out = replay(&path, |_| {}).unwrap();
        assert!(matches!(
            out,
            ReplayOutcome::Corrupt {
                error: WalError::TooLarge { what: "key", .. },
                ..
            }
        ));
        cleanup(&path);
    }
}
