// examples/ex05-wal-record-parse.rs —— WAL record 解析：魔数 + CRC 校验 + 零拷贝 key/value 视图
// 对应主文档 3.8。演示一套「KV 日志」record 的解析：固定头部 + 变长 key/value 载荷，
// 头部字段逐个用「长度检查 + try_into」，key/value 以借用切片返回（解析全程零分配），
// CRC 校验先于任何业务使用 —— 不可信字节进内存的第一道闸门是完整性校验。
// record 格式（教学简化，字段一律小端）：
//   [magic: u32][crc: u32（对 key||value 求值）][seq: u64][op: u8]
//   [klen: u32][vlen: u32][key][value]      op: 1=Put 2=Delete（Delete 时 vlen==0）
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行：
//   rustc --edition 2021 -D warnings ex05-wal-record-parse.rs -o /tmp/ph19-ex05 && /tmp/ph19-ex05
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。
use std::fmt;

const MAGIC: u32 = 0x5741_4C31; // b"WAL1"
const OP_PUT: u8 = 1;
const OP_DELETE: u8 = 2;
/// 固定头部字节数 = magic4 + crc4 + seq8 + op1 + klen4 + vlen4 = 25
const HEADER_LEN: usize = 25;

/// 一条已解析的 WAL record。key/value 借用自输入缓冲 —— 记日志 / 交给上层都不用搬数据。
#[derive(Debug, PartialEq, Eq)]
struct WalRecord<'a> {
    seq: u64,
    op: Op,
    key: &'a [u8],
    value: &'a [u8], // Delete 时为空切片
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Op {
    Put,
    Delete,
}

/// 解析单条 record：从 buf 头部读，返回 record 与其占用的总字节数。
fn parse_record<'a>(buf: &'a [u8]) -> Result<(WalRecord<'a>, usize), WalErr> {
    let head = buf.get(..HEADER_LEN).ok_or(WalErr::Truncated)?;
    // —— 安全纪律：先魔数定位（快速排除垃圾），再 CRC 校验完整性，最后才拆业务字段 ——
    let magic = u32::from_le_bytes(head[0..4].try_into().map_err(|_| WalErr::Truncated)?);
    if magic != MAGIC {
        return Err(WalErr::BadMagic(magic));
    }
    let expect_crc = u32::from_le_bytes(head[4..8].try_into().map_err(|_| WalErr::Truncated)?);
    let seq = u64::from_le_bytes(head[8..16].try_into().map_err(|_| WalErr::Truncated)?);
    let op = match head[16] {
        OP_PUT => Op::Put,
        OP_DELETE => Op::Delete,
        other => return Err(WalErr::UnknownOp(other)),
    };
    let klen = u32::from_le_bytes(head[17..21].try_into().map_err(|_| WalErr::Truncated)?) as usize;
    let vlen = u32::from_le_bytes(head[21..25].try_into().map_err(|_| WalErr::Truncated)?) as usize;
    // key/value 定界，全程 checked 区间切取，越界即截断
    let key = buf.get(HEADER_LEN..HEADER_LEN + klen).ok_or(WalErr::Truncated)?;
    let value = buf
        .get(HEADER_LEN + klen..HEADER_LEN + klen + vlen)
        .ok_or(WalErr::Truncated)?;
    // 完整性校验：把真实算出的 CRC 与头部声明值对齐（数据损坏在解析入口被拦下）
    let actual = crc32_combine(key, value);
    if actual != expect_crc {
        return Err(WalErr::ChecksumMismatch { expect: expect_crc, actual });
    }
    let total = HEADER_LEN + klen + vlen;
    Ok((WalRecord { seq, op, key, value }, total))
}

/// 逐条遍历一段「多条 record 追加成的 WAL」：从头游走，剩 0 字节即干净结束。
fn replay<'a>(log: &'a [u8]) -> Result<Vec<(WalRecord<'a>, usize)>, WalErr> {
    let mut out = Vec::new();
    let mut pos = 0usize;
    while pos < log.len() {
        let (rec, used) = parse_record(&log[pos..])?;
        pos += used;
        out.push((rec, used));
    }
    Ok(out)
}

// —— 极简 CRC32（IEEE，教学版，逐位实现） ——
// 工程上可直接用 crc32fast / crc32c crate；这里零第三方演示「校验和怎么算」。
// ⚠️ 教学简化：逐位计算较慢且非常数时间，正式存储请换成熟库，勿在热路径照抄。
const CRC_INIT: u32 = 0xFFFF_FFFF;
const CRC_POLY: u32 = 0xEDB8_8320; // IEEE 802.3（以太网）多项式

/// 对 key||value 串行求 CRC：两段迭代器接龙，不分配、不复制（保持零拷贝承诺）。
fn crc32_combine(key: &[u8], value: &[u8]) -> u32 {
    let mut crc = CRC_INIT;
    for &b in key.iter().chain(value.iter()) {
        crc = crc32_step(crc, b);
    }
    crc ^ CRC_INIT
}

fn crc32_step(mut crc: u32, byte: u8) -> u32 {
    crc ^= byte as u32;
    for _ in 0..8 {
        let mask = (crc & 1).wrapping_neg();
        crc = (crc >> 1) ^ (CRC_POLY & mask);
    }
    crc
}

#[derive(Debug)]
enum WalErr {
    BadMagic(u32),
    Truncated,
    ChecksumMismatch { expect: u32, actual: u32 },
    UnknownOp(u8),
}

impl fmt::Display for WalErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            WalErr::BadMagic(m) => write!(f, "魔数错误：0x{m:08X}（不是 WAL1，可能不同格式/错位）"),
            WalErr::Truncated => write!(f, "数据截断：record 声明长度超过可用字节"),
            WalErr::ChecksumMismatch { expect, actual } => {
                write!(f, "CRC 校验失败：声明 0x{expect:08X}，实算 0x{actual:08X}（数据已损坏）")
            }
            WalErr::UnknownOp(op) => write!(f, "未知操作码：{op}"),
        }
    }
}

fn main() {
    // —— 0. CRC 实现自检：IEEE 标准测试向量 "123456789" → 0xCBF43926 ——
    println!("== CRC32 自检 ==");
    let probe = crc32_combine(b"123456789", b"");
    println!("crc32(\"123456789\") = 0x{probe:08X}（期望 0xCBF43926）");
    assert_eq!(probe, 0xCBF4_3926, "CRC 实现与 IEEE 测试向量不一致");
    assert_eq!(crc32_combine(b"", b""), 0, "空串 CRC 应为 0");
    println!("自检通过");
    println!();

    // —— 1. 构造日志：Put 与 Delete 各一条，追加进同一段缓冲 ——
    println!("== 构造 WAL 日志 ==");
    let mut log = Vec::new();
    append_record(&mut log, 1001, Op::Put, b"temperature", b"36.5");
    append_record(&mut log, 1002, Op::Delete, b"humidity", b"");
    println!("日志共 {} 字节（两条 record）", log.len());
    // 实测输出：日志共 73 字节 = (25 + 11 + 4) + (25 + 8 + 0)（key "temperature"=11B，value "36.5"=4B）

    // —— 2. 零拷贝解析 + 回放 ——
    println!();
    println!("== replay 解析 ==");
    for (i, (rec, used)) in replay(&log).expect("合法日志").into_iter().enumerate() {
        println!(
            "第 {i} 条：seq={} op={:?} key={:?} value={:?} 占用 {used} 字节",
            rec.seq,
            rec.op,
            String::from_utf8_lossy(rec.key),
            String::from_utf8_lossy(rec.value)
        );
    }
    // 实测输出（第 0 条 seq=1001 Put key="temperature" value="36.5"；第 1 条 seq=1002 Delete key="humidity"）

    // —— 3. 篡改测试：改一个 key 字节 → CRC 拦下 ——
    println!();
    println!("== 完整性校验 ==");
    let mut tampered = log.clone();
    tampered[HEADER_LEN + 5] ^= 0x01; // 翻转 key 中间一个字节
    match replay(&tampered) {
        Ok(_) => println!("意外通过（不应发生）"),
        Err(e) => println!("篡改日志 → {e}"),
    }
    // 实测输出：篡改日志 → CRC 校验失败：声明 0x……，实算 0x……（数据已损坏）

    // —— 4. 错误路径：坏魔数 / 截断 ——
    println!();
    println!("== 其余错误路径 ==");
    let mut bad_magic = log.clone();
    bad_magic[0] = 0x00;
    println!("坏魔数 → {:?}", replay(&bad_magic).err().expect("应失败"));
    let cut = &log[..log.len() - 3]; // 砍掉尾 3 字节 → 最后一条 record 不完整
    println!("截断   → {:?}", replay(cut).err().expect("应失败"));
}

/// 编码一条 record 并追加进 log（教学用编码器：与解析器字段严格镜像）。
fn append_record(log: &mut Vec<u8>, seq: u64, op: Op, key: &[u8], value: &[u8]) {
    let crc = crc32_combine(key, value);
    log.extend_from_slice(&MAGIC.to_le_bytes());
    log.extend_from_slice(&crc.to_le_bytes());
    log.extend_from_slice(&seq.to_le_bytes());
    log.push(match op {
        Op::Put => OP_PUT,
        Op::Delete => OP_DELETE,
    });
    log.extend_from_slice(&(key.len() as u32).to_le_bytes());
    log.extend_from_slice(&(value.len() as u32).to_le_bytes());
    log.extend_from_slice(key);
    log.extend_from_slice(value);
}
