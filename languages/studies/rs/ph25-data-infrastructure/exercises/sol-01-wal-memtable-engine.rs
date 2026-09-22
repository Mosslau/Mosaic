// exercises/sol-01-wal-memtable-engine.rs —— 练习 1 参考实现：WAL + MemTable 一体迷你引擎
// 对应 roadmap §25 练习「实现 WAL append / replay 与 MemTable」与主文档 3.1。
// record 磁盘布局（大端，与 C/ph16、cpp/ph22 对齐）：
//   [magic u32 = 0x57414C31 "WAL1"][type u8:1=put 2=del][klen u32][vlen u32][key][value][crc32 u32]
//   CRC 覆盖 [type..value]（magic 不参与）——连操作码与长度字段一起校验。
// 本文件是「从零实现」：不用 examples/ex01 的库代码，把同一套纪律再写一遍。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-01-wal-memtable-engine.rs -o /tmp/ph25-sol01 && /tmp/ph25-sol01
//   rustc --edition 2021 -D warnings --test sol-01-wal-memtable-engine.rs -o /tmp/ph25-sol01-t && /tmp/ph25-sol01-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。

use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

const MAGIC: u32 = 0x5741_4C31;
const HEADER_LEN: usize = 13; // magic4 + type1 + klen4 + vlen4
const MAX_KEY: usize = 1 << 20;
const MAX_VALUE: usize = 1 << 20;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Op {
    Put,
    Delete,
}

#[derive(Debug)]
enum EngError {
    TooLarge { what: &'static str, len: usize },
    UnknownOp(u8),
    Io(std::io::Error),
}

impl std::fmt::Display for EngError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EngError::TooLarge { what, len } => write!(f, "{what} 长度 {len} 超上限"),
            EngError::UnknownOp(op) => write!(f, "未知操作码 {op}"),
            EngError::Io(e) => write!(f, "I/O：{e}"),
        }
    }
}
impl std::error::Error for EngError {}
impl From<std::io::Error> for EngError {
    fn from(e: std::io::Error) -> Self {
        EngError::Io(e)
    }
}

// —— CRC32（IEEE 802.3，查表）——
const CRC_TABLE: [u32; 256] = make_table();
const fn make_table() -> [u32; 256] {
    let mut t = [0u32; 256];
    let mut i = 0usize;
    while i < 256 {
        let mut c = i as u32;
        let mut k = 0;
        while k < 8 {
            c = if c & 1 == 1 { 0xEDB8_8320 ^ (c >> 1) } else { c >> 1 };
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

fn be32(bytes: &[u8]) -> u32 {
    u32::from_be_bytes([bytes[0], bytes[1], bytes[2], bytes[3]])
}

fn put_be32(buf: &mut Vec<u8>, v: u32) {
    buf.extend_from_slice(&v.to_be_bytes());
}

/// 迷你引擎：WAL（磁盘）+ MemTable（内存有序表）。
///
/// 写入路径：put/delete → 先编码 record 追加进日志文件 → 再改内存表。
/// 崩溃恢复：open 时重放日志重建内存表，残尾（写了一半的记录）自动截断。
struct MiniEngine {
    file: File,
    mem: BTreeMap<Vec<u8>, Vec<u8>>,
    /// open 时是否发生了残尾截断（供演示/测试观察）。
    recovered_torn: bool,
}

impl MiniEngine {
    /// 打开（或新建）一个引擎：有旧日志则重放并修复残尾。
    fn open(dir: &Path) -> Result<MiniEngine, EngError> {
        std::fs::create_dir_all(dir)?;
        let path = dir.join("engine.wal");
        let mut file = OpenOptions::new()
            .create(true)
            .read(true)
            .write(true)
            .open(&path)?;
        let mut mem = BTreeMap::new();
        // 读整段日志
        let mut buf = Vec::new();
        file.read_to_end(&mut buf)?;
        let clean_end = replay(&buf, &mut mem)?;
        let recovered_torn = (clean_end as usize) < buf.len();
        if recovered_torn {
            // 残尾：把文件截到最后一个完整 record 之后
            file.set_len(clean_end)?;
            file.sync_all()?;
        }
        // 无论是否截断，把写游标放到文件尾（截断后原游标可能在 EOF 之外，
        // 直接写会把「零字节空洞」写进日志——必须在 set_len 后重新 seek）。
        file.seek(SeekFrom::End(0))?;
        Ok(MiniEngine {
            file,
            mem,
            recovered_torn,
        })
    }

    fn put(&mut self, key: &[u8], value: &[u8]) -> Result<(), EngError> {
        self.append_record(Op::Put, key, value)?;
        self.mem.insert(key.to_vec(), value.to_vec());
        Ok(())
    }

    fn delete(&mut self, key: &[u8]) -> Result<(), EngError> {
        self.append_record(Op::Delete, key, &[])?;
        self.mem.remove(key);
        Ok(())
    }

    fn get(&self, key: &[u8]) -> Option<&[u8]> {
        self.mem.get(key).map(Vec::as_slice)
    }

    /// fsync 落盘。**append 返回 ≠ 持久化**：数据只在内核页缓存，
    /// `flush()`（fsync）返回才算「崩溃后还在」——写路径必须回答提交粒度。
    fn flush(&mut self) -> Result<(), EngError> {
        self.file.sync_all()?;
        Ok(())
    }

    fn append_record(&mut self, op: Op, key: &[u8], value: &[u8]) -> Result<(), EngError> {
        if key.len() > MAX_KEY {
            return Err(EngError::TooLarge { what: "key", len: key.len() });
        }
        if value.len() > MAX_VALUE {
            return Err(EngError::TooLarge { what: "value", len: value.len() });
        }
        let mut buf = Vec::with_capacity(HEADER_LEN + key.len() + value.len() + 4);
        put_be32(&mut buf, MAGIC);
        buf.push(match op {
            Op::Put => 1,
            Op::Delete => 2,
        });
        put_be32(&mut buf, key.len() as u32);
        put_be32(&mut buf, value.len() as u32);
        buf.extend_from_slice(key);
        buf.extend_from_slice(value);
        let crc = crc32(&buf[4..]); // CRC 覆盖 type..value
        put_be32(&mut buf, crc);
        self.file.write_all(&buf)?;
        Ok(())
    }
}

/// 重放日志到内存表；返回「最后一个完整 record 之后的字节偏移」。
fn replay(buf: &[u8], mem: &mut BTreeMap<Vec<u8>, Vec<u8>>) -> Result<u64, EngError> {
    let mut pos = 0usize;
    while buf.len() - pos >= HEADER_LEN {
        let head = &buf[pos..pos + HEADER_LEN];
        if be32(&head[0..4]) != MAGIC {
            return Ok(pos as u64); // 损坏：截断到当前位置
        }
        let op = match head[4] {
            1 => Op::Put,
            2 => Op::Delete,
            other => {
                return Err(EngError::UnknownOp(other));
            }
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
            return Ok(pos as u64); // 尾部不够装完整 record：残尾，截断
        }
        let expect = be32(&buf[record_end..record_end + 4]);
        let actual = crc32(&buf[pos + 4..record_end]);
        if expect != actual {
            return Ok(pos as u64); // CRC 不过：视为残尾/损坏，截断（崩溃残写多落在此）
        }
        let key = &buf[pos + HEADER_LEN..pos + HEADER_LEN + klen];
        let value = &buf[pos + HEADER_LEN + klen..record_end];
        match op {
            Op::Put => {
                mem.insert(key.to_vec(), value.to_vec());
            }
            Op::Delete => {
                mem.remove(key);
            }
        }
        pos = record_end + 4;
    }
    Ok(pos as u64)
}

fn demo_dir(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("ph25-sol01-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    d
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // —— 场景 1：20 次交错 put/delete → flush → 关闭 → 重开状态一致 ——
    let dir = demo_dir("s1");
    {
        let mut eng = MiniEngine::open(&dir)?;
        for i in 0..20u32 {
            eng.put(format!("key{i:02}").as_bytes(), format!("v{i}").as_bytes())?;
            if i % 4 == 0 {
                eng.delete(format!("key{i:02}").as_bytes())?;
            }
        }
        eng.flush()?; // fsync：模拟「进程此刻崩溃也不丢已 flush 记录」
    } // 这里 drop，模拟关闭/崩溃窗口
    let eng = MiniEngine::open(&dir)?;
    let mut ok = true;
    for i in 0..20u32 {
        let want = if i % 4 == 0 {
            None
        } else {
            Some(format!("v{i}").into_bytes())
        };
        if eng.get(format!("key{i:02}").as_bytes()).map(Vec::from) != want {
            ok = false;
            eprintln!("重开后 key{i:02} 状态不符");
        }
    }
    assert!(ok, "重开状态应与崩溃前完全一致");
    println!(
        "[场景 1] 20 次交错 put/delete + flush 后重开：状态一致 ✓（{} 个存活 key）",
        eng.mem.len()
    );

    // —— 场景 2：手工塞 5 字节残尾 → 重开自动截断且能继续写 ——
    let dir2 = demo_dir("s2");
    {
        let mut eng = MiniEngine::open(&dir2)?;
        eng.put(b"k1", b"v1")?;
        eng.flush()?;
        drop(eng);
        let mut f = OpenOptions::new().append(true).open(dir2.join("engine.wal"))?;
        f.write_all(&[0x57, 0x41, 0x4C, 0x01, 0x00])?; // 半条记录
        f.sync_all()?;
    }
    let mut eng2 = MiniEngine::open(&dir2)?;
    assert!(eng2.recovered_torn, "应检测到残尾");
    assert_eq!(eng2.get(b"k1"), Some(&b"v1"[..]));
    eng2.put(b"k2", b"v2")?;
    eng2.flush()?;
    drop(eng2);
    let eng2b = MiniEngine::open(&dir2)?;
    assert_eq!(eng2b.get(b"k2"), Some(&b"v2"[..]));
    assert!(!eng2b.recovered_torn);
    println!(
        "[场景 2] 5 字节残尾 → 重开自动截断修复（recovered_torn=true），随后还能继续写 ✓"
    );

    // —— 场景 3：翻转 payload 一字节 → 重开停在损坏点之前，不崩溃 ——
    let dir3 = demo_dir("s3");
    {
        let mut eng = MiniEngine::open(&dir3)?;
        eng.put(b"important", b"value1")?;
        eng.put(b"second", b"value2")?;
        eng.flush()?;
        drop(eng);
        let first_total = (HEADER_LEN + b"important".len() + b"value1".len() + 4) as u64;
        let mut f = OpenOptions::new().read(true).write(true).open(dir3.join("engine.wal"))?;
        f.seek(SeekFrom::Start(first_total + HEADER_LEN as u64))?; // 第二条 key 首字节
        let mut b = [0u8; 1];
        f.read_exact(&mut b)?;
        b[0] ^= 0xFF;
        f.seek(SeekFrom::Start(first_total + HEADER_LEN as u64))?;
        f.write_all(&b)?;
        f.sync_all()?;
    }
    let eng3 = MiniEngine::open(&dir3)?;
    assert_eq!(eng3.get(b"important"), Some(&b"value1"[..]), "损坏点之前的记录应保留");
    assert_eq!(eng3.get(b"second"), None, "损坏点之后不再信任");
    assert!(eng3.recovered_torn, "位翻转按残尾处理并截断");
    println!(
        "[场景 3] payload 位翻转 → 重开保留损坏点前记录、丢弃损坏点后记录、不崩溃 ✓"
    );

    println!("\n练习 1 参考实现自检通过：WAL append/replay + MemTable + 残尾修复全部符合预期");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!(
            "ph25-sol01-test-{name}-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&d);
        d
    }

    #[test]
    fn roundtrip_restores_state() {
        let dir = temp("roundtrip");
        {
            let mut e = MiniEngine::open(&dir).unwrap();
            e.put(b"a", b"1").unwrap();
            e.put(b"b", b"2").unwrap();
            e.delete(b"a").unwrap();
            e.flush().unwrap();
        }
        let e = MiniEngine::open(&dir).unwrap();
        assert_eq!(e.get(b"a"), None);
        assert_eq!(e.get(b"b"), Some(&b"2"[..]));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn torn_tail_truncated_on_open() {
        let dir = temp("torn");
        {
            let mut e = MiniEngine::open(&dir).unwrap();
            e.put(b"k", b"v").unwrap();
            e.flush().unwrap();
            drop(e);
            let mut f = OpenOptions::new().append(true).open(dir.join("engine.wal")).unwrap();
            f.write_all(&[0x57, 0x41, 0x4C, 0x01]).unwrap();
        }
        let e = MiniEngine::open(&dir).unwrap();
        assert!(e.recovered_torn);
        assert_eq!(e.get(b"k"), Some(&b"v"[..]));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn corrupted_payload_stops_at_point() {
        let dir = temp("flip");
        {
            let mut e = MiniEngine::open(&dir).unwrap();
            e.put(b"first", b"1").unwrap();
            e.put(b"second", b"2").unwrap();
            e.flush().unwrap();
            drop(e);
            let first_total = (HEADER_LEN + 5 + 1 + 4) as u64;
            let mut f = OpenOptions::new().read(true).write(true).open(dir.join("engine.wal")).unwrap();
            f.seek(SeekFrom::Start(first_total + HEADER_LEN as u64)).unwrap();
            let mut b = [0u8; 1];
            f.read_exact(&mut b).unwrap();
            b[0] ^= 1;
            f.seek(SeekFrom::Start(first_total + HEADER_LEN as u64)).unwrap();
            f.write_all(&b).unwrap();
            f.sync_all().unwrap();
        }
        let e = MiniEngine::open(&dir).unwrap();
        assert_eq!(e.get(b"first"), Some(&b"1"[..]));
        assert_eq!(e.get(b"second"), None);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn crc_ieee_vector() {
        assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
    }
}
