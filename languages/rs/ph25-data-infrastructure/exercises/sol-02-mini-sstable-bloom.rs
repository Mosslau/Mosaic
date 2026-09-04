// exercises/sol-02-mini-sstable-bloom.rs —— 练习 2 参考实现：Mini SSTable writer/reader + Bloom
// 对应 roadmap §25 练习「实现 Mini SSTable writer / reader 并增加 Bloom Filter」与主文档 3.2/3.3。
// 自定字节布局（大端，单层、无 block 的教学简化）：
//   entries 区：n × [klen u32][key][vlen u32][value]（key 升序、不重复）
//   offsets 区：n × [entry 起始偏移 u64]
//   bloom 区：  [m u64][k u32][位图字节]
//   trailer：   [magic u32 = 0x53535432 "SST2"][n u32][offsets_len u64][bloom_len u64]（定长 24B）
// 本文件从零实现：不用 examples/ex02 的代码，布局思路同源但自写。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-02-mini-sstable-bloom.rs -o /tmp/ph25-sol02 && /tmp/ph25-sol02
//   rustc --edition 2021 -D warnings --test sol-02-mini-sstable-bloom.rs -o /tmp/ph25-sol02-t && /tmp/ph25-sol02-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。

use std::collections::BTreeMap;

const MAGIC: u32 = 0x5353_5432;
const TRAILER_LEN: usize = 24; // magic4 + n4 + offsets_len8 + bloom_len8
const MAX_KEY: usize = 1 << 20;
const MAX_VALUE: usize = 1 << 20;

#[derive(Debug)]
enum TblError {
    BadMagic { got: u32 },
    TooShort,
    Corrupt,
    OutOfOrder,
}

impl std::fmt::Display for TblError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TblError::BadMagic { got } => write!(f, "魔数 0x{got:08X} 不符"),
            TblError::TooShort => write!(f, "文件过短，不足一个 trailer"),
            TblError::Corrupt => write!(f, "结构损坏（偏移/长度越界）"),
            TblError::OutOfOrder => write!(f, "输入 key 未升序"),
        }
    }
}
impl std::error::Error for TblError {}

fn be32(b: &[u8]) -> u32 {
    u32::from_be_bytes([b[0], b[1], b[2], b[3]])
}
fn be64(b: &[u8]) -> u64 {
    u64::from_be_bytes([b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7]])
}

// —— FNV-1a 双散列 Bloom（确定性，零依赖）——
fn fnv1a(data: &[u8], seed: u64) -> u64 {
    let mut h = 0xcbf2_9ce4_8422_2325u64 ^ seed;
    for &b in data {
        h ^= u64::from(b);
        h = h.wrapping_mul(0x0000_0100_0000_01B3);
    }
    h
}

struct Bloom {
    bits: Vec<u8>,
    m: u64,
    k: u32,
}

impl Bloom {
    fn new(n: usize, bits_per_key: usize) -> Bloom {
        let m = (n.saturating_mul(bits_per_key).max(64) as u64).next_power_of_two();
        let k = ((std::f64::consts::LN_2 * m as f64 / n.max(1) as f64).round() as u32).clamp(1, 16);
        Bloom { bits: vec![0u8; ((m / 8) + 1) as usize], m, k }
    }

    fn positions(&self, key: &[u8]) -> Vec<u64> {
        let h1 = fnv1a(key, 0);
        let h2 = fnv1a(key, 0x9E37_79B9_7F4A_7C15) | 1;
        (0..self.k)
            .map(|i| h1.wrapping_add(u64::from(i).wrapping_mul(h2)) % self.m)
            .collect()
    }

    fn add(&mut self, key: &[u8]) {
        for p in self.positions(key) {
            self.bits[(p / 8) as usize] |= 1 << (p % 8);
        }
    }

    /// 无假阴性：false = 一定不在；true = 可能存在，需进一步查证。
    fn may_contain(&self, key: &[u8]) -> bool {
        self.positions(key)
            .into_iter()
            .all(|p| self.bits[(p / 8) as usize] & (1 << (p % 8)) != 0)
    }

    fn encode(&self, out: &mut Vec<u8>) {
        out.extend_from_slice(&self.m.to_be_bytes());
        out.extend_from_slice(&self.k.to_be_bytes());
        out.extend_from_slice(&self.bits);
    }

    fn decode(buf: &[u8]) -> Bloom {
        Bloom {
            m: be64(&buf[0..8]),
            k: be32(&buf[8..12]),
            bits: buf[12..].to_vec(),
        }
    }
}

struct Stats {
    entries: usize,
    offsets_bytes: usize,
    bloom_m: u64,
    bloom_k: u32,
    file_bytes: usize,
}

/// 写 SSTable：输入必须已按 key 严格升序。返回字节镜像 + 统计。
fn write_sstable(
    entries: &[(Vec<u8>, Vec<u8>)],
    bits_per_key: usize,
) -> Result<(Vec<u8>, Stats), TblError> {
    let mut data = Vec::new();
    let mut offsets = Vec::with_capacity(entries.len());
    let mut last: Option<&[u8]> = None;
    for (k, v) in entries {
        if k.is_empty() {
            continue; // 空 key 无意义；空 value（vlen=0）允许编码
        }
        if let Some(prev) = last {
            if k.as_slice() <= prev {
                return Err(TblError::OutOfOrder);
            }
        }
        if k.len() > MAX_KEY || v.len() > MAX_VALUE {
            return Err(TblError::Corrupt);
        }
        offsets.push(data.len() as u64);
        data.extend_from_slice(&(k.len() as u32).to_be_bytes());
        data.extend_from_slice(k);
        data.extend_from_slice(&(v.len() as u32).to_be_bytes());
        data.extend_from_slice(v);
        last = Some(k);
    }
    let n = offsets.len();
    let mut out = data;
    for off in &offsets {
        out.extend_from_slice(&off.to_be_bytes());
    }
    // bloom 区：对全部 key 建位图
    let mut bloom = Bloom::new(n, bits_per_key);
    for (k, _) in entries {
        if !k.is_empty() {
            bloom.add(k);
        }
    }
    let bloom_off = out.len();
    bloom.encode(&mut out);
    let bloom_len = out.len() - bloom_off;
    // trailer（定长 24B，读侧据此定位三个区域）
    out.extend_from_slice(&MAGIC.to_be_bytes());
    out.extend_from_slice(&(n as u32).to_be_bytes());
    out.extend_from_slice(&(offsets.len() as u64 * 8).to_be_bytes());
    out.extend_from_slice(&(bloom_len as u64).to_be_bytes());
    let stats = Stats {
        entries: n,
        offsets_bytes: offsets.len() * 8,
        bloom_m: bloom.m,
        bloom_k: bloom.k,
        file_bytes: out.len(),
    };
    Ok((out, stats))
}

/// 表读取器：open 时解析 trailer → offsets → key 索引 → Bloom。
/// 点查：Bloom 拦截 → 二分定位 → 只解析那一条 entry；scan：从 lower_bound 顺序读。
struct Table {
    buf: Vec<u8>,
    n: usize,
    index: Vec<(Vec<u8>, usize)>, // (key, entry 偏移)，升序
    bloom: Bloom,
}

impl Table {
    fn open(buf: Vec<u8>) -> Result<Table, TblError> {
        if buf.len() < TRAILER_LEN {
            return Err(TblError::TooShort);
        }
        let tpos = buf.len() - TRAILER_LEN;
        let magic = be32(&buf[tpos..tpos + 4]);
        if magic != MAGIC {
            return Err(TblError::BadMagic { got: magic });
        }
        let n = be32(&buf[tpos + 4..tpos + 8]) as usize;
        let offsets_len = be64(&buf[tpos + 8..tpos + 16]) as usize;
        let bloom_len = be64(&buf[tpos + 16..tpos + 24]) as usize;
        if offsets_len != n * 8 {
            return Err(TblError::Corrupt);
        }
        let offsets_off = buf.len() - TRAILER_LEN - bloom_len - offsets_len;
        let bloom_off = offsets_off + offsets_len;
        // 读 offsets + 逐条读 key 建索引
        let mut index = Vec::with_capacity(n);
        for i in 0..n {
            let off_pos = offsets_off + i * 8;
            let entry_off = be64(&buf[off_pos..off_pos + 8]) as usize;
            let (_klen, key, _vpos) = read_key(&buf, entry_off)?;
            index.push((key, entry_off));
        }
        let bloom = Bloom::decode(&buf[bloom_off..buf.len() - TRAILER_LEN]);
        Ok(Table { buf, n, index, bloom })
    }

    /// 读出 entry_off 处一条 entry 的 (klen,key,vlen) 并把整条解析出来。
    fn read_entry(&self, off: usize) -> Result<(Vec<u8>, Vec<u8>), TblError> {
        let b = &self.buf;
        let (_klen, key, vpos) = read_key(b, off)?;
        let vlen = be32(&b[vpos..vpos + 4]) as usize;
        if vlen > MAX_VALUE || vpos + 4 + vlen > b.len() {
            return Err(TblError::Corrupt);
        }
        Ok((key, b[vpos + 4..vpos + 4 + vlen].to_vec()))
    }

    /// 点查。返回 `Ok(Some(v))` 命中 / `Ok(None)` 确定不存在。
    fn get(&self, key: &[u8]) -> Result<Option<Vec<u8>>, TblError> {
        if !self.bloom.may_contain(key) {
            return Ok(None); // Bloom 无假阴性：false = 一定没有
        }
        let i = self.index.partition_point(|(k, _)| k.as_slice() < key);
        if i == self.n {
            return Ok(None);
        }
        let (k, off) = &self.index[i];
        if k.as_slice() != key {
            return Ok(None);
        }
        let (_, v) = self.read_entry(*off)?;
        Ok(Some(v))
    }

    /// range scan：[start, end] 闭区间，按 key 升序返回。
    fn scan(&self, start: &[u8], end: &[u8]) -> Result<Vec<(Vec<u8>, Vec<u8>)>, TblError> {
        let mut out = Vec::new();
        let mut i = self.index.partition_point(|(k, _)| k.as_slice() < start);
        while i < self.n {
            let (k, off) = &self.index[i];
            if k.as_slice() > end {
                break;
            }
            let (key, v) = self.read_entry(*off)?;
            out.push((key, v));
            i += 1;
        }
        Ok(out)
    }
}

/// 从 entry 头部读出 klen/key，并返回 vlen 字段所在位置。
fn read_key(b: &[u8], off: usize) -> Result<(usize, Vec<u8>, usize), TblError> {
    if off + 4 > b.len() {
        return Err(TblError::Corrupt);
    }
    let klen = be32(&b[off..off + 4]) as usize;
    if klen > MAX_KEY || off + 4 + klen + 4 > b.len() {
        return Err(TblError::Corrupt);
    }
    let key = b[off + 4..off + 4 + klen].to_vec();
    Ok((klen, key, off + 4 + klen))
}


fn main() -> Result<(), Box<dyn std::error::Error>> {
    // —— 构造 500 个有序 key 的表并写盘 ——
    let mut entries: BTreeMap<Vec<u8>, Vec<u8>> = BTreeMap::new();
    for i in 0..500u32 {
        entries.insert(
            format!("key{i:04}").into_bytes(),
            format!("value-of-{i:04}").into_bytes(),
        );
    }
    let sorted: Vec<(Vec<u8>, Vec<u8>)> = entries.into_iter().collect();
    let (img, stats) = write_sstable(&sorted, 10)?;
    println!(
        "[构建] {} 条 / {} B（offsets {} B / bloom m={} k={}）",
        stats.entries, stats.file_bytes, stats.offsets_bytes, stats.bloom_m, stats.bloom_k
    );

    // 写盘 → 读回（练习要求走一遍真实文件 I/O）
    let path = std::env::temp_dir().join(format!("ph25-sol02-{}.sst", std::process::id()));
    std::fs::write(&path, &img)?;
    let bytes = std::fs::read(&path)?;
    let _ = std::fs::remove_file(&path);
    let tbl = Table::open(bytes)?;

    // —— 全量 get 验证 + miss ——
    let mut all_hit = true;
    for i in 0..500u32 {
        let got = tbl.get(format!("key{i:04}").as_bytes())?;
        if got.as_deref() != Some(format!("value-of-{i:04}").as_bytes()) {
            all_hit = false;
        }
    }
    assert!(all_hit, "500 个 key 应全部命中且值正确");
    println!("[点查] 500 个 key round-trip：全部命中、值正确 ✓");
    assert_eq!(tbl.get(b"key9999")?, None, "范围外 key 应为 None");
    assert_eq!(tbl.get(b"zzz")?, None, "不存在的 key 应为 None");
    println!("[点查] 不存在的 key → None ✓");

    // —— Bloom 假阳性率实测 ——
    let fp = (0..500u32)
        .filter(|i| tbl.bloom.may_contain(format!("nokey{i:04}").as_bytes()))
        .count();
    println!("[Bloom] 500 个不存在的 key 中 {} 个判 maybe（假阳性率 {:.2}%）", fp, fp as f64 / 5.0);
    assert!(fp as f64 / 500.0 <= 0.05, "FP 率应 ≤5%");

    // —— range scan ——
    let rows = tbl.scan(b"key0100", b"key0104")?;
    assert_eq!(rows.len(), 5);
    assert_eq!(rows[0].0, b"key0100");
    assert_eq!(rows[4].0, b"key0104");
    println!("[scan] key0100..=key0104 → {} 条，升序正确 ✓", rows.len());

    // —— 反序输入拒绝 ——
    let mut bad = sorted.clone();
    bad.reverse();
    assert!(matches!(write_sstable(&bad, 10), Err(TblError::OutOfOrder)));
    println!("[输入] 反序 key 被拒绝（OutOfOrder）✓");

    println!("\n练习 2 参考实现自检通过：SSTable round-trip / Bloom 拦截 / scan / 反序拒绝全部符合预期");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bloom_no_false_negative() {
        let mut b = Bloom::new(100, 10);
        for i in 0..100u32 {
            b.add(format!("p{i:03}").as_bytes());
        }
        for i in 0..100u32 {
            assert!(b.may_contain(format!("p{i:03}").as_bytes()));
        }
    }

    #[test]
    fn roundtrip_and_miss() {
        let mut m: BTreeMap<Vec<u8>, Vec<u8>> = BTreeMap::new();
        m.insert(b"a".to_vec(), b"1".to_vec());
        m.insert(b"b".to_vec(), b"2".to_vec());
        m.insert(b"c".to_vec(), b"3".to_vec());
        let sorted: Vec<_> = m.into_iter().collect();
        let (img, _) = write_sstable(&sorted, 10).unwrap();
        let t = Table::open(img).unwrap();
        assert_eq!(t.get(b"a").unwrap(), Some(b"1".to_vec()));
        assert_eq!(t.get(b"c").unwrap(), Some(b"3".to_vec()));
        assert_eq!(t.get(b"z").unwrap(), None);
    }

    #[test]
    fn scan_range() {
        let mut m: BTreeMap<Vec<u8>, Vec<u8>> = BTreeMap::new();
        for i in 0..50u32 {
            m.insert(format!("k{i:02}").into_bytes(), vec![]);
        }
        let sorted: Vec<_> = m.into_iter().collect();
        let (img, _) = write_sstable(&sorted, 10).unwrap();
        let t = Table::open(img).unwrap();
        let rows = t.scan(b"k10", b"k19").unwrap();
        assert_eq!(rows.len(), 10);
        assert_eq!(rows[0].0, b"k10");
        assert_eq!(rows[9].0, b"k19");
    }

    #[test]
    fn unsorted_rejected() {
        let e = vec![(b"b".to_vec(), b"1".to_vec()), (b"a".to_vec(), b"2".to_vec())];
        assert!(matches!(write_sstable(&e, 10), Err(TblError::OutOfOrder)));
    }

    #[test]
    fn garbage_rejected() {
        assert!(matches!(Table::open(vec![1, 2, 3]), Err(TblError::TooShort)));
    }
}
