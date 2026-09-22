// examples/ex02-byteorder.rs —— 字节序：大端/小端读写、from_be_bytes/to_be_bytes、安全的头部读取器
// 对应主文档 3.3。演示：网络序（大端）读写固定宽度整数、读长度不足返回 None 的纪律、
// 手写一个纯 std 的 BigEndianReader（零第三方，也是 bytes::Buf get_uXX 的「裸机版」）。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行：
//   rustc --edition 2021 -D warnings ex02-byteorder.rs -o /tmp/ph19-ex02 && /tmp/ph19-ex02
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin，macOS 为小端机 → 恰好演示与网络序的换算）。
use std::fmt;

/// 手工 BE 读取器：所有读都做「长度检查 + try_into 定长数组」，绝不越界也不 panic。
/// 核心思路（主文档 3.2/3.7）：u16::from_be_bytes 接受的是 [u8; 2]（按值），
/// 从 &[u8] 切片获得定长数组的唯一正道是 buf.get(..n)?.try_into()?。
struct BeReader<'a> {
    buf: &'a [u8],
    pos: usize,
}

impl<'a> BeReader<'a> {
    fn new(buf: &'a [u8]) -> Self {
        BeReader { buf, pos: 0 }
    }

    /// 读 n 个字节；不足则返回 None（调用方用 ? 传播，体现「长度检查」纪律）
    fn take(&mut self, n: usize) -> Option<&'a [u8]> {
        let end = self.pos.checked_add(n)?;
        let chunk = self.buf.get(self.pos..end)?;
        self.pos = end;
        Some(chunk)
    }

    fn u8(&mut self) -> Option<u8> {
        self.take(1).map(|c| c[0])
    }

    /// 大端（网络序）读 u16：先取 2 字节，再按大端组装
    fn u16_be(&mut self) -> Option<u16> {
        let bytes: [u8; 2] = self.take(2)?.try_into().ok()?;
        Some(u16::from_be_bytes(bytes))
    }

    fn u32_be(&mut self) -> Option<u32> {
        let bytes: [u8; 4] = self.take(4)?.try_into().ok()?;
        Some(u32::from_be_bytes(bytes))
    }

    fn u64_be(&mut self) -> Option<u64> {
        let bytes: [u8; 8] = self.take(8)?.try_into().ok()?;
        Some(u64::from_be_bytes(bytes))
    }

    fn remaining(&self) -> usize {
        self.buf.len() - self.pos
    }
}

fn main() {
    // —— 1. 常数级换算：be/le 只是「字节排列方向」，数字本身不因字节序改变 ——
    let n: u32 = 0x1234_5678;
    println!("== 基础换算（数字 {} = 0x1234_5678）==", n);
    println!("to_be_bytes : {:02X?}", n.to_be_bytes());
    println!("to_le_bytes : {:02X?}", n.to_le_bytes());
    println!("to_ne_bytes : {:02X?}", n.to_ne_bytes()); // 本机（aarch64）与 le 相同
    println!("从 le 读回   : {}", u32::from_le_bytes(n.to_le_bytes()));
    // 实测输出：
    //   to_be_bytes : [12, 34, 56, 78]   ← 大端：高字节在前，网络传输/磁盘落盘多用
    //   to_le_bytes : [78, 56, 34, 12]   ← 小端：低字节在前，x86/ARM 原生
    //   to_ne_bytes : [78, 56, 34, 12]   ← 本机字节序（不做持久化/跨机通信时用）
    //   from_le_bytes 读回 = 305419896，恒等于原值

    // —— 2. 字符串的坑：b"AB" 与数组字面量的类型差异 ——
    // u16::from_be_bytes([b'A', b'B']) = 0x4142 = 16706；注意 b"AB" 是 &[u8; 2]，不能直接喂给需要数组的函数
    println!();
    println!("== 字符串即字节 ==");
    println!("[b'A', b'B'] 大端读作 u16 = 0x{:04X}", u16::from_be_bytes([b'A', b'B']));
    // 顺带用上 BeReader::u16_be：b"AB" 切片进入读取器后按大端读出 0x4142
    let mut tiny = BeReader::new(b"AB");
    let v = tiny.u16_be().expect("2 字节在");
    println!("BeReader 读 b\"AB\" → 0x{v:04X}（读走 2 字节，剩余 {} 字节）", tiny.remaining());

    // —— 3. 手工 BE 读取器：解析「type + seq + ts」固定头部 ——
    println!();
    println!("== BeReader 解析固定头部（3.2 练习的雏形）==");
    // 组包：type=1B, seq=u32 BE, ts=u64 BE —— 与下方 parse_fixed_header 的字段定义完全一致
    let mut head = Vec::new();
    head.push(0x2Au8);
    head.extend_from_slice(&1_700_000_000u32.to_be_bytes());
    head.extend_from_slice(&1_700_000_123u64.to_be_bytes());
    let mut r = BeReader::new(&head);
    let ty = r.u8().expect("类型字节");
    let seq = r.u32_be().expect("序列号");
    let ts = r.u64_be().expect("时间戳");
    println!("type=0x{ty:02X} seq={seq} ts={ts} 剩余={} 字节", r.remaining());
    // 实测输出：type=0x2A seq=1700000000 ts=1700000123 剩余=0 字节

    // —— 4. 长度检查：buffer 不足时不 panic，返回 None ——
    println!();
    println!("== 长度不足的安全行为 ==");
    let truncated = &head[..5]; // 故意只给 5 字节（缺 ts 的 8 字节）
    let mut r2 = BeReader::new(truncated);
    let _ = r2.u8();
    let _ = r2.u8();
    let _ = r2.u32_be();
    match r2.u64_be() {
        Some(v) => println!("意外读到 {v}"),
        None => println!("ts 读取返回 None（仅 5 字节，差 8 字节）——调用方据 ? 传播错误，无 panic"),
    }

    // —— 5. Display 侧的错误闭环（rust-patterns：错误走 Result，不裸 unwrap）——
    println!();
    println!("== 组合成 Result ==");
    match parse_fixed_header(&head) {
        Ok(h) => println!("parse_fixed_header → {h}"),
        Err(e) => println!("解析失败：{e}"),
    }
    match parse_fixed_header(truncated) {
        Ok(h) => println!("truncated 意外成功：{h}"),
        Err(e) => println!("truncated → {e}"),
    }
}

/// 简化固定头部：type(1B) + seq(u32 BE) + ts(u64 BE)。返回 Result，绝不 panic。
fn parse_fixed_header(buf: &[u8]) -> Result<FixedHeader, ParseErr> {
    let mut r = BeReader::new(buf);
    let ty = r.u8().ok_or(ParseErr::Truncated)?;
    let seq = r.u32_be().ok_or(ParseErr::Truncated)?;
    let ts = r.u64_be().ok_or(ParseErr::Truncated)?;
    Ok(FixedHeader { ty, seq, ts })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct FixedHeader {
    ty: u8,
    seq: u32,
    ts: u64,
}

impl fmt::Display for FixedHeader {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "FixedHeader{{type=0x{:02X}, seq={}, ts={}}}", self.ty, self.seq, self.ts)
    }
}

/// 极简错误类型（仅教学需要，省略 thiserror；完整自定义错误体系见 ph11）
#[derive(Debug)]
enum ParseErr {
    Truncated,
}

impl fmt::Display for ParseErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ParseErr::Truncated => write!(f, "buffer 长度不足（截断）"),
        }
    }
}
