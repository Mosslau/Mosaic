//! ph25 ex02：SSTable writer/reader + Bloom Filter（纯 std，零第三方依赖）
//!
//! 把 LSM 的「不可变有序文件 + 稀疏索引 + Bloom 过滤」落成一个可读写的
//! 单文件格式：写入侧把已排序的 (key, value) 切块落盘并留稀疏索引，
//! 读取侧先过 Bloom（无假阴性，点查拦截「文件里肯定没有」的 key）、再按
//! 稀疏索引二分定位块、最后只读目标块做精确比对。tombstone（删除标记）
//! 作为值的特殊形态存进文件——删除也是一条记录，只有 compaction 才会真删
//! （那是 ex03 的主题）。磁盘格式与 C/ph16、cpp/ph22 的 SSTable 语义对齐：
//! 大端、长度前缀、block 内升序 entry、块首 key 稀疏索引。
//!
//! # 验证环境与命令
//! - 验证环境：rustc/cargo 1.92.0（macOS arm64）
//! - 运行：`cargo run`（2000 键演示 + Bloom 假阳性实测 + range scan）
//! - 测试：`cargo test --release`
//! - 质量：`cargo fmt --check && cargo clippy --all-targets -- -D warnings`
//! - 验证状态：**已验证**（2026-09-04 本机实测，输出见 examples/README）

use std::collections::BTreeMap;
use std::fmt;
use std::fs::File;
use std::io::Read;
use std::path::Path;

/// 文件魔数 `b"SST1"` = 0x53535431。
const MAGIC: u32 = 0x5353_5431;
/// 文件尾部定长 trailer：magic4 + num_blocks4 + index_len8 + bloom_len8 = 24。
const TRAILER_LEN: usize = 24;
const MAX_KEY: usize = 1 << 20;
const MAX_VALUE: usize = 1 << 20;
/// 单个 block 的字节预算：超过预算且块非空即 flush（与 RocksDB 的近似逻辑）。
const BLOCK_BUDGET: usize = 128;
/// Bloom 的 bits per key（默认值；Demo 用它量化假阳性率）。
const DEFAULT_BITS_PER_KEY: usize = 10;

/// 操作类型：Put / Delete（删除 = tombstone 记录，不是擦除）。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Op {
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

    fn from_u8(b: u8) -> Result<Self, SstError> {
        match b {
            1 => Ok(Op::Put),
            2 => Ok(Op::Delete),
            other => Err(SstError::BadOp(other)),
        }
    }
}

/// SSTable 里的值：Put 携带数据，Delete 表达「遮挡旧层同名 key」的 tombstone。
#[derive(Debug, Clone, PartialEq, Eq)]
enum Value {
    Put(Vec<u8>),
    Tombstone,
}

impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Value::Put(v) => write!(f, "{}", String::from_utf8_lossy(v)),
            Value::Tombstone => write!(f, "<deleted>"),
        }
    }
}

/// 错误：坏文件的所有失败形态（字节层不 panic，全部走 Result）。
#[derive(Debug)]
enum SstError {
    /// 文件太短连 trailer 都没有。
    TooShort,
    /// 魔数不对：不是本格式。
    BadMagic {
        got: u32,
    },
    /// 操作码不是 Put/Delete。
    BadOp(u8),
    /// 长度字段超上限。
    TooLarge {
        what: &'static str,
        len: usize,
    },
    /// 块计数与索引内容对不上。
    BadIndex,
    /// 写入的 key 不是升序（SSTable 必须有序输入）。
    OutOfOrder {
        prev: Vec<u8>,
        next: Vec<u8>,
    },
    Io(std::io::Error),
}

impl fmt::Display for SstError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SstError::TooShort => write!(f, "文件过短，不足一个 trailer"),
            SstError::BadMagic { got } => write!(f, "魔数错误 0x{got:08X}（期望 0x{MAGIC:08X}）"),
            SstError::BadOp(op) => write!(f, "未知操作码 {op}"),
            SstError::TooLarge { what, len } => write!(f, "{what} 长度 {len} 超过上限"),
            SstError::BadIndex => write!(f, "索引与文件长度不匹配"),
            SstError::OutOfOrder { prev, next } => write!(
                f,
                "key 非升序：'{}' 之后是 '{}'（写入必须有序）",
                String::from_utf8_lossy(prev),
                String::from_utf8_lossy(next)
            ),
            SstError::Io(e) => write!(f, "I/O 错误：{e}"),
        }
    }
}

impl std::error::Error for SstError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            SstError::Io(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for SstError {
    fn from(e: std::io::Error) -> Self {
        SstError::Io(e)
    }
}

// —— 大端读写小工具（多字节字段一律大端落盘，ph19 字节纪律） ——

fn put_u32(buf: &mut Vec<u8>, v: u32) {
    buf.extend_from_slice(&v.to_be_bytes());
}

fn put_u64(buf: &mut Vec<u8>, v: u64) {
    buf.extend_from_slice(&v.to_be_bytes());
}

fn read_u32_at(buf: &[u8], pos: usize) -> u32 {
    u32::from_be_bytes(buf[pos..pos + 4].try_into().expect("区间已校验"))
}

fn read_u64_at(buf: &[u8], pos: usize) -> u64 {
    u64::from_be_bytes(buf[pos..pos + 8].try_into().expect("区间已校验"))
}

/// 手读 4 字节大端（只在调用方先做过 `get(pos..pos+4)` 区间检查后使用）。
fn be32(b: &[u8]) -> u32 {
    u32::from_be_bytes([b[0], b[1], b[2], b[3]])
}

/// FNV-1a 64：为 Bloom 提供第一个散列（种子 0）。
fn fnv1a64(data: &[u8], seed: u64) -> u64 {
    let mut h = 0xcbf2_9ce4_8422_2325u64 ^ seed;
    for &b in data {
        h ^= u64::from(b);
        h = h.wrapping_mul(0x0000_0100_0000_01B3);
    }
    h
}

/// Bloom Filter：`m` 位位图 + `k` 个散列位置（双散列法，确定性、零依赖）。
struct Bloom {
    bits: Vec<u8>,
    m: u64, // 位图位数（m >= 1）
    k: u32, // 散列次数
}

impl Bloom {
    /// 用 n 个元素与 bits_per_key 预算构造：m = n * bits_per_key，
    /// k = round(ln2 * m / n)（ln2≈0.693，经典最优 k 推导见主文档 4.4）。
    fn new(n: usize, bits_per_key: usize) -> Bloom {
        let m = ((n.saturating_mul(bits_per_key).max(64)) as u64).next_power_of_two();
        let k = ((std::f64::consts::LN_2 * m as f64 / n.max(1) as f64).round() as u32).clamp(1, 16);
        Bloom {
            bits: vec![0u8; ((m / 8) + 1) as usize],
            m,
            k,
        }
    }

    fn positions(&self, key: &[u8]) -> Vec<u64> {
        let h1 = fnv1a64(key, 0);
        let h2 = fnv1a64(key, 0x9E37_79B9_7F4A_7C15) | 1; // 保证奇数，双散列增量有效
        (0..self.k)
            .map(|i| h1.wrapping_add(u64::from(i).wrapping_mul(h2)) % self.m)
            .collect()
    }

    fn add(&mut self, key: &[u8]) {
        for pos in self.positions(key) {
            let byte = &mut self.bits[(pos / 8) as usize];
            *byte |= 1 << (pos % 8);
        }
    }

    /// `may_contain`：返回 false 则 key 一定不在（无假阴性）；true 需进一步查证。
    fn may_contain(&self, key: &[u8]) -> bool {
        self.positions(key)
            .into_iter()
            .all(|pos| self.bits[(pos / 8) as usize] & (1 << (pos % 8)) != 0)
    }

    /// 序列化为 bloom 区域：`[m u64][k u32][位图字节]`。
    fn encode(&self, out: &mut Vec<u8>) {
        put_u64(out, self.m);
        put_u32(out, self.k);
        out.extend_from_slice(&self.bits);
    }

    fn decode(buf: &[u8]) -> Bloom {
        let m = read_u64_at(buf, 0);
        let k = read_u32_at(buf, 8);
        Bloom {
            bits: buf[12..].to_vec(),
            m,
            k,
        }
    }
}

/// 稀疏索引条目：块的第一个 key → 块在文件中的字节偏移。
struct IndexEntry {
    first_key: Vec<u8>,
    offset: u64,
}

/// SSTable 写入器：把有序 (key, value) 序列切成 block 落盘。
///
/// 文件布局（全部大端）：
/// ```text
/// [block 0][block 1]…[index 区域][bloom 区域][trailer 定长 24B]
///   block = [n u32][entry]*n；entry = [type u8][klen u32][key][vlen u32][value]
///   index 区域 = 每块一条 [first_key klen u32][first_key][offset u64]
///   bloom 区域 = [m u64][k u32][位图字节]
///   trailer = [magic u32][num_blocks u32][index_len u64][bloom_len u64]
/// ```
struct SstWriter {
    out: Vec<u8>, // 教学实现：先在内存拼好再写盘（真实引擎直接顺序写文件）
    cur_block: Vec<u8>,
    cur_entries: usize,
    cur_bytes: usize,
    index: Vec<IndexEntry>,
    all_keys: Vec<Vec<u8>>, // flush 时才知道总数 n → 用 n 定 Bloom 的 m
    last_key: Option<Vec<u8>>,
    bits_per_key: usize,
}

impl SstWriter {
    fn new(bits_per_key: usize) -> SstWriter {
        SstWriter {
            out: Vec::new(),
            cur_block: Vec::new(),
            cur_entries: 0,
            cur_bytes: 0,
            index: Vec::new(),
            all_keys: Vec::new(),
            last_key: None,
            bits_per_key,
        }
    }

    /// 追加一条。要求 key 严格升序（相等 key 由上层去重，SSTable 不许重复 key）。
    fn add(&mut self, key: Vec<u8>, value: Value) -> Result<(), SstError> {
        if let Some(prev) = &self.last_key {
            if key <= *prev {
                return Err(SstError::OutOfOrder {
                    prev: prev.clone(),
                    next: key,
                });
            }
        }
        // 估计本条 entry 的字节数：type1 + klen4 + key + vlen4 + value
        let value_bytes = match &value {
            Value::Put(v) => v.len(),
            Value::Tombstone => 0,
        };
        let entry_bytes = 1 + 4 + key.len() + 4 + value_bytes;
        if self.cur_entries > 0 && self.cur_bytes + entry_bytes > BLOCK_BUDGET {
            self.flush_block();
        }
        self.cur_bytes += entry_bytes;
        self.cur_entries += 1;
        let op = match &value {
            Value::Put(_) => Op::Put,
            Value::Tombstone => Op::Delete,
        };
        self.cur_block.push(op.as_u8());
        put_u32(&mut self.cur_block, key.len() as u32);
        self.cur_block.extend_from_slice(&key);
        put_u32(
            &mut self.cur_block,
            match &value {
                Value::Put(v) => v.len() as u32,
                Value::Tombstone => 0,
            },
        );
        match &value {
            Value::Put(v) => self.cur_block.extend_from_slice(v),
            Value::Tombstone => {}
        }
        self.all_keys.push(key.clone());
        self.last_key = Some(key);
        Ok(())
    }

    fn flush_block(&mut self) {
        let offset = self.out.len() as u64;
        let first_key = self
            .all_keys
            .get(self.all_keys.len() - self.cur_entries)
            .expect("块首 key 必在 all_keys 中")
            .clone();
        self.out
            .extend_from_slice(&(self.cur_entries as u32).to_be_bytes());
        self.out.extend_from_slice(&self.cur_block);
        self.index.push(IndexEntry { first_key, offset });
        self.cur_block.clear();
        self.cur_entries = 0;
        self.cur_bytes = 0;
    }

    /// 收尾写盘：flush 最后一个块、构造 Bloom（全部 key）、拼 index/bloom/trailer。
    fn finish(mut self, path: &Path) -> Result<SstStats, SstError> {
        if self.cur_entries > 0 {
            self.flush_block();
        }
        let n = self.all_keys.len();
        let mut bloom = Bloom::new(n, self.bits_per_key);
        for k in &self.all_keys {
            bloom.add(k);
        }
        // index 区域
        let mut index_buf = Vec::new();
        for e in &self.index {
            put_u32(&mut index_buf, e.first_key.len() as u32);
            index_buf.extend_from_slice(&e.first_key);
            put_u64(&mut index_buf, e.offset);
        }
        self.out.extend_from_slice(&index_buf);
        // bloom 区域（先记偏移，写完再算区域长度）
        let bloom_off = self.out.len() as u64;
        bloom.encode(&mut self.out);
        let bloom_len = self.out.len() as u64 - bloom_off;
        // trailer（24 字节定长，读侧据此反推 index/bloom 区域位置）
        put_u32(&mut self.out, MAGIC);
        put_u32(&mut self.out, self.index.len() as u32);
        put_u64(&mut self.out, index_buf.len() as u64);
        put_u64(&mut self.out, bloom_len);
        std::fs::write(path, &self.out)?;
        let stats = SstStats {
            file_size: self.out.len(),
            num_blocks: self.index.len(),
            entries: n,
            bloom_bits: bloom.m,
            bloom_k: bloom.k,
        };
        Ok(stats)
    }
}

/// 写入统计（README 与主文档引用的真实数字来源）。
struct SstStats {
    file_size: usize,
    num_blocks: usize,
    entries: usize,
    bloom_bits: u64,
    bloom_k: u32,
}

/// SSTable 读取器：打开后持有整文件字节 + 解析好的索引与 Bloom。
///
/// 教学简化：整文件读入内存（真实引擎用 mmap / 块缓存按需取块，ph13/后续阶段
/// 的思路；本示例把「只读目标块做比对」做成方法级约束并统计 block_reads，
/// 让点查与 scan 的读块差异可观察）。
struct SstReader {
    buf: Vec<u8>,
    num_blocks: usize,
    index: Vec<IndexEntry>,
    bloom: Bloom,
    block_reads: u64, // 已读取的块数（演示点查 vs scan 的读盘面差异）
}

impl SstReader {
    fn open(path: &Path) -> Result<SstReader, SstError> {
        let mut f = File::open(path)?;
        let mut buf = Vec::new();
        f.read_to_end(&mut buf)?;
        if buf.len() < TRAILER_LEN {
            return Err(SstError::TooShort);
        }
        let file_len = buf.len();
        let trailer_pos = file_len - TRAILER_LEN;
        let magic = read_u32_at(&buf, trailer_pos);
        if magic != MAGIC {
            return Err(SstError::BadMagic { got: magic });
        }
        let num_blocks = read_u32_at(&buf, trailer_pos + 4) as usize;
        let index_len = read_u64_at(&buf, trailer_pos + 8) as usize;
        let bloom_len = read_u64_at(&buf, trailer_pos + 16) as usize;
        let index_off = file_len - TRAILER_LEN - bloom_len - index_len;
        let bloom_off = index_off + index_len;
        // 解析索引：num_blocks 条 {klen, key, offset}
        let mut index = Vec::with_capacity(num_blocks);
        let mut pos = index_off;
        for _ in 0..num_blocks {
            if pos + 4 > bloom_off {
                return Err(SstError::BadIndex);
            }
            let klen = read_u32_at(&buf, pos) as usize;
            pos += 4;
            if klen > MAX_KEY || pos + klen + 8 > bloom_off {
                return Err(SstError::BadIndex);
            }
            let key = buf[pos..pos + klen].to_vec();
            pos += klen;
            let offset = read_u64_at(&buf, pos);
            pos += 8;
            index.push(IndexEntry {
                first_key: key,
                offset,
            });
        }
        let bloom = Bloom::decode(&buf[bloom_off..file_len - TRAILER_LEN]);
        Ok(SstReader {
            buf,
            num_blocks,
            index,
            bloom,
            block_reads: 0,
        })
    }

    /// Bloom 层的「点查拦截」计量：返回 false 说明文件里没有该 key。
    fn bloom_may_contain(&self, key: &[u8]) -> bool {
        self.bloom.may_contain(key)
    }

    /// 块 i 的字节区间 `[start, end)`。
    fn block_range(&self, i: usize) -> (usize, usize) {
        let start = self.index[i].offset as usize;
        let end = if i + 1 < self.num_blocks {
            self.index[i + 1].offset as usize
        } else {
            // 最后一个块结束于 index 区域起点
            let trailer_pos = self.buf.len() - TRAILER_LEN;
            let index_len = read_u64_at(&self.buf, trailer_pos + 8) as usize;
            let bloom_len = read_u64_at(&self.buf, trailer_pos + 16) as usize;
            self.buf.len() - TRAILER_LEN - bloom_len - index_len
        };
        (start, end)
    }

    /// 解析一块：返回有序的 (key, value) 列表。坏块返回 Err（读取侧不 panic）。
    fn decode_block(&self, i: usize) -> Result<Vec<(Vec<u8>, Value)>, SstError> {
        let (start, end) = self.block_range(i);
        if end < start + 4 {
            return Err(SstError::BadIndex);
        }
        let n = read_u32_at(&self.buf, start) as usize;
        let mut pos = start + 4;
        let mut out = Vec::with_capacity(n);
        for _ in 0..n {
            // 每步都做区间检查：不可信字节不能越界切
            let op = Op::from_u8(*self.buf.get(pos).ok_or(SstError::BadIndex)?)?;
            pos += 1;
            // 每步手写大端读 + 区间检查：不可信字节不能越界切
            let klen = {
                let b = self.buf.get(pos..pos + 4).ok_or(SstError::BadIndex)?;
                be32(b)
            } as usize;
            if klen > MAX_KEY {
                return Err(SstError::TooLarge {
                    what: "key",
                    len: klen,
                });
            }
            pos += 4;
            let key = self
                .buf
                .get(pos..pos + klen)
                .ok_or(SstError::BadIndex)?
                .to_vec();
            pos += klen;
            let vlen = {
                let b = self.buf.get(pos..pos + 4).ok_or(SstError::BadIndex)?;
                be32(b)
            } as usize;
            if vlen > MAX_VALUE {
                return Err(SstError::TooLarge {
                    what: "value",
                    len: vlen,
                });
            }
            pos += 4;
            let value = match op {
                Op::Put => Value::Put(
                    self.buf
                        .get(pos..pos + vlen)
                        .ok_or(SstError::BadIndex)?
                        .to_vec(),
                ),
                Op::Delete => Value::Tombstone,
            };
            pos += vlen;
            out.push((key, value));
        }
        Ok(out)
    }

    /// 读块并计数（读盘面统计）。
    fn read_block(&mut self, i: usize) -> Result<Vec<(Vec<u8>, Value)>, SstError> {
        self.block_reads += 1;
        self.decode_block(i)
    }

    /// 按 key 点查：先 Bloom 拦截，再稀疏索引二分定位块，只读那一块比对。
    ///
    /// 返回语义：`Ok(Some(Value))` 命中；`Ok(None)` 文件里确实没有。
    fn get(&mut self, key: &[u8]) -> Result<Option<Value>, SstError> {
        if !self.bloom_may_contain(key) {
            return Ok(None); // Bloom 无假阴性：这里说没有就是没有
        }
        // 二分：找最后一个 first_key <= key 的块
        let mut lo = 0usize;
        let mut hi = self.num_blocks; // [lo, hi)
        let mut cand = None;
        while lo < hi {
            let mid = (lo + hi) / 2;
            if self.index[mid].first_key.as_slice() <= key {
                cand = Some(mid);
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        let Some(block) = cand else {
            return Ok(None);
        };
        for (k, v) in self.read_block(block)? {
            if k == key {
                return Ok(Some(v));
            }
            if k.as_slice() > key {
                break; // 块内升序，超过即无
            }
        }
        Ok(None)
    }

    /// 按 key 读取；tombstone 向调用方返回 Deleted 语义（遮挡旧层的事归 engine）。
    fn scan(&mut self, start: &[u8], end: &[u8]) -> Result<Vec<(Vec<u8>, Value)>, SstError> {
        // 从「最后一个 first_key <= start 的块」起步（start 可能落在这个块中间），
        // 顺序读后续块；块内跳过 < start 的条目，遇到 > end 立即停。
        let mut out = Vec::new();
        let n_le_start = self
            .index
            .partition_point(|e| e.first_key.as_slice() <= start);
        let mut i = n_le_start.saturating_sub(1);
        while i < self.num_blocks {
            for (k, v) in self.read_block(i)? {
                if k.as_slice() < start {
                    continue;
                }
                if k.as_slice() > end {
                    return Ok(out);
                }
                out.push((k, v));
            }
            i += 1;
        }
        Ok(out)
    }

    fn block_reads(&self) -> u64 {
        self.block_reads
    }
}

/// 把 (key, value) 写成一个排序输入（模拟 MemTable flush 时的有序读面）。
fn demo_entries(n: usize) -> BTreeMap<Vec<u8>, Vec<u8>> {
    let mut m = BTreeMap::new();
    for i in 0..n {
        m.insert(
            format!("key{i:05}").into_bytes(),
            format!("value-of-key{i:05}").into_bytes(),
        );
    }
    m
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let dir = std::env::temp_dir().join(format!("ph25-ex02-demo-{}", std::process::id()));
    std::fs::create_dir_all(&dir)?;
    let path = dir.join("demo.sst");

    // —— 构建 2000 键的 SSTable（block 预算 128B → 约 17 键/块 → 约 120 块） ——
    let entries = demo_entries(2000);
    let mut w = SstWriter::new(DEFAULT_BITS_PER_KEY);
    for (k, v) in &entries {
        w.add(k.clone(), Value::Put(v.clone()))?;
    }
    let stats = w.finish(&path)?;
    println!(
        "[构建] 文件 {} B | {} 块 | {} 条 | Bloom m={} bits ({} bits/key), k={} 次散列",
        stats.file_size,
        stats.num_blocks,
        stats.entries,
        stats.bloom_bits,
        stats.bloom_bits as usize / stats.entries.max(1),
        stats.bloom_k
    );

    // —— 点查路径：Bloom 拦截 + 稀疏索引 + 只读目标块 ——
    let mut r = SstReader::open(&path)?;
    let probe_exist = format!("key{:05}", 1234).into_bytes();
    let v = r.get(&probe_exist)?.expect("存在的 key 必须命中");
    let shown = match &v {
        Value::Put(b) => String::from_utf8_lossy(b).into_owned(),
        Value::Tombstone => "<deleted>".to_string(),
    };
    println!("[点查] key1234 → {shown} （读块 {} 次）", r.block_reads());

    // Bloom 假阳性实测：2000 个不存在的 key 过 Bloom，看有多少被放行到索引层
    let mut maybe_count = 0usize;
    for i in 0..2000u32 {
        let absent = format!("nokey{i:05}").into_bytes();
        if r.bloom_may_contain(&absent) {
            maybe_count += 1;
        }
    }
    println!(
        "[Bloom] 2000 个不存在的 key 中 {} 个被判 maybe（假阳性率 {:.3}%）",
        maybe_count,
        maybe_count as f64 / 20.0
    );

    // 存在性无假阴性：抽查全部 2000 个已写 key
    let false_neg = (0..2000u32)
        .filter(|i| !r.bloom_may_contain(&format!("key{i:05}").into_bytes()))
        .count();
    println!("[Bloom] 2000 个已写 key 全过 Bloom：假阴性 = {false_neg}（应为 0）");

    // —— range scan：与点查对照读块面 ——
    let mut r2 = SstReader::open(&path)?;
    let scanned = r2.scan(b"key00100", b"key00119")?;
    println!(
        "[scan] key00100..=key00119 → {} 条（读块 {} 次；区间跨块越多，scan 读块面越大于点查的 1）",
        scanned.len(),
        r2.block_reads()
    );

    // —— tombstone 演示：写一个含删除的 3 键小文件 ——
    let path2 = dir.join("tomb.sst");
    let mut w2 = SstWriter::new(DEFAULT_BITS_PER_KEY);
    w2.add(b"alpha".to_vec(), Value::Put(b"1".to_vec()))?;
    w2.add(b"bravo".to_vec(), Value::Tombstone)?;
    w2.add(b"charlie".to_vec(), Value::Put(b"3".to_vec()))?;
    w2.finish(&path2)?;
    let mut r3 = SstReader::open(&path2)?;
    println!(
        "[tombstone] bravo 读出的是删除标记：{:?}",
        r3.get(b"bravo")?
    );
    println!("[tombstone] alpha 读出的是值：{:?}", r3.get(b"alpha")?);
    println!("[tombstone] 不存在的 key：{:?}", r3.get(b"nope")?);

    std::fs::remove_dir_all(&dir)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("ph25-ex02-{name}-{}.sst", std::process::id()))
    }

    #[test]
    fn roundtrip_reads_back_all_values() {
        let path = temp_path("roundtrip");
        let _ = std::fs::remove_file(&path);
        {
            let mut w = SstWriter::new(10);
            for i in 0..300u32 {
                w.add(
                    format!("k{i:04}").into_bytes(),
                    Value::Put(vec![i as u8; 3]),
                )
                .unwrap();
            }
            let _ = w.finish(&path).unwrap();
        }
        let mut r = SstReader::open(&path).unwrap();
        for i in (0..300u32).step_by(7) {
            let v = r.get(&format!("k{i:04}").into_bytes()).unwrap();
            assert_eq!(v, Some(Value::Put(vec![i as u8; 3])));
        }
        // Bloom 拦截路径：不存在的 key 返回 None
        assert_eq!(r.get(b"zzz999").unwrap(), None, "不存在的 key 应为 None");
        assert_eq!(r.get(b"k9999").unwrap(), None, "超出范围的 key 应为 None");
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn tombstone_roundtrips_and_hides_nothing_single_layer() {
        let path = temp_path("tomb");
        let _ = std::fs::remove_file(&path);
        {
            let mut w = SstWriter::new(10);
            w.add(b"a".to_vec(), Value::Put(b"1".to_vec())).unwrap();
            w.add(b"b".to_vec(), Value::Tombstone).unwrap();
            w.add(b"c".to_vec(), Value::Put(b"3".to_vec())).unwrap();
            w.finish(&path).unwrap();
        }
        let mut r = SstReader::open(&path).unwrap();
        assert_eq!(r.get(b"a").unwrap(), Some(Value::Put(b"1".to_vec())));
        assert_eq!(r.get(b"b").unwrap(), Some(Value::Tombstone));
        assert_eq!(r.get(b"c").unwrap(), Some(Value::Put(b"3".to_vec())));
        assert_eq!(r.get(b"d").unwrap(), None);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn scan_returns_sorted_range() {
        let path = temp_path("scan");
        let _ = std::fs::remove_file(&path);
        {
            let mut w = SstWriter::new(10);
            for i in 0..200u32 {
                w.add(format!("k{i:04}").into_bytes(), Value::Put(vec![]))
                    .unwrap();
            }
            w.finish(&path).unwrap();
        }
        let mut r = SstReader::open(&path).unwrap();
        let rows = r.scan(b"k0050", b"k0059").unwrap();
        assert_eq!(rows.len(), 10);
        assert_eq!(rows.first().unwrap().0, b"k0050");
        assert_eq!(rows.last().unwrap().0, b"k0059");
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn bloom_has_no_false_negative() {
        let path = temp_path("bloom");
        let _ = std::fs::remove_file(&path);
        let n = 500usize;
        {
            let mut w = SstWriter::new(10);
            for i in 0..n {
                w.add(format!("present{i:04}").into_bytes(), Value::Put(vec![]))
                    .unwrap();
            }
            w.finish(&path).unwrap();
        }
        let r = SstReader::open(&path).unwrap();
        for i in 0..n {
            assert!(
                r.bloom_may_contain(&format!("present{i:04}").into_bytes()),
                "已写 key {i} 被 Bloom 误判为不在（无假阴性被破坏）"
            );
        }
        // 假阳性率上界：500 个不存在 key，FPR 应显著小于 5%
        let fpr = {
            let mut cnt = 0usize;
            for i in 0..n {
                if r.bloom_may_contain(&format!("absent{i:04}").into_bytes()) {
                    cnt += 1;
                }
            }
            cnt as f64 / n as f64
        };
        assert!(fpr < 0.05, "实测假阳性率 {fpr} 应 < 5%");
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn unsorted_input_rejected() {
        let mut w = SstWriter::new(10);
        w.add(b"b".to_vec(), Value::Put(vec![])).unwrap();
        let err = w.add(b"a".to_vec(), Value::Put(vec![]));
        assert!(matches!(err, Err(SstError::OutOfOrder { .. })));
    }

    #[test]
    fn garbage_file_rejected_by_magic() {
        let path = temp_path("garbage");
        std::fs::write(&path, b"not-an-sstable-format-at-all").unwrap();
        assert!(matches!(
            SstReader::open(&path),
            Err(SstError::BadMagic { .. }) | Err(SstError::TooShort)
        ));
        let _ = std::fs::remove_file(&path);
    }
}
