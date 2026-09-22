// exercises/sol-01-fixed-header.rs —— 练习 1 参考实现：解析固定头部二进制协议（含大端/小端混合字段）
// 对应 roadmap 第 19 节练习「解析固定头部二进制协议（含大端/小端字段）」与主文档 3.3/3.7。
// 格式规范（练习自定，注意同时出现 BE 与 LE）：
//   [magic: "FX" 2B][ty: u16 LE][seq: u32 BE][ts: u64 LE][plen: u16 BE][payload…]
// 解析纪律：逐字段 get + try_into + from_*_bytes；长度不足返回 Err 不 panic；头部解析后 payload 借用不复制。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-01-fixed-header.rs -o /tmp/ph19-sol01 && /tmp/ph19-sol01
//   rustc --edition 2021 -D warnings --test sol-01-fixed-header.rs -o /tmp/ph19-sol01-t && /tmp/ph19-sol01-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。
use std::fmt;

const HEADER_LEN: usize = 2 + 2 + 4 + 8 + 2; // magic + ty + seq + ts + plen = 18

#[derive(Debug, PartialEq, Eq)]
struct FixedHeader<'a> {
    ty: u16,
    seq: u32,
    ts: u64,
    payload: &'a [u8], // 借用输入，零拷贝
}

/// 头部 + payload 整体解析：读完头部后按 plen 切 payload（先长度闸门再切）。
fn parse_packet<'a>(buf: &'a [u8]) -> Result<FixedHeader<'a>, HeaderErr> {
    let head = buf.get(..HEADER_LEN).ok_or(HeaderErr::Truncated)?;
    if &head[0..2] != b"FX" {
        return Err(HeaderErr::BadMagic);
    }
    let ty = u16::from_le_bytes(head[2..4].try_into().map_err(|_| HeaderErr::Truncated)?);
    let seq = u32::from_be_bytes(head[4..8].try_into().map_err(|_| HeaderErr::Truncated)?);
    let ts = u64::from_le_bytes(head[8..16].try_into().map_err(|_| HeaderErr::Truncated)?);
    let plen = u16::from_be_bytes(head[16..18].try_into().map_err(|_| HeaderErr::Truncated)?) as usize;
    let payload = buf.get(HEADER_LEN..HEADER_LEN + plen).ok_or(HeaderErr::Truncated)?;
    Ok(FixedHeader { ty, seq, ts, payload })
}

#[derive(Debug, PartialEq, Eq)]
enum HeaderErr {
    Truncated,
    BadMagic,
}

impl fmt::Display for HeaderErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            HeaderErr::Truncated => write!(f, "头部/载荷截断（长度不足）"),
            HeaderErr::BadMagic => write!(f, "魔数不是 FX"),
        }
    }
}

fn build_packet(ty: u16, seq: u32, ts: u64, payload: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    out.extend_from_slice(b"FX");
    out.extend_from_slice(&ty.to_le_bytes());
    out.extend_from_slice(&seq.to_be_bytes());
    out.extend_from_slice(&ts.to_le_bytes());
    out.extend_from_slice(&(payload.len() as u16).to_be_bytes());
    out.extend_from_slice(payload);
    out
}

fn main() {
    let packet = build_packet(0x0102, 3_000_000_000, 1_700_000_000_000_123, b"hello");
    println!("包长 {} 字节", packet.len());
    // 手算核对（可先自己算再对）：magic 2 + ty 2 + seq 4 + ts 8 + plen 2 + payload 5 = 23
    match parse_packet(&packet) {
        Ok(h) => println!(
            "ty=0x{:04X}(LE) seq={}(BE) ts={}(LE) payload={:?}",
            h.ty, h.seq, h.ts, String::from_utf8_lossy(h.payload)
        ),
        Err(e) => println!("解析失败：{e}"),
    }

    // 错误路径：截断在 ts 中间、坏魔数
    println!("截断 → {:?}", parse_packet(&packet[..12]).err().expect("应失败").to_string());
    let mut bad = packet.clone();
    bad[0] = b'X';
    println!("坏魔数 → {:?}", parse_packet(&bad).err().expect("应失败").to_string());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_mixed_endian_fields() {
        let p = build_packet(0x0102, 3_000_000_000, 1_700_000_000_000_123, b"hello");
        let h = parse_packet(&p).expect("合法包");
        assert_eq!(h.ty, 0x0102);
        assert_eq!(h.seq, 3_000_000_000);
        assert_eq!(h.ts, 1_700_000_000_000_123);
        assert_eq!(h.payload, b"hello");
    }

    #[test]
    fn payload_is_borrowed_not_copied() {
        let p = build_packet(1, 2, 3, b"abcdef");
        let h = parse_packet(&p).expect("合法包");
        // 载荷视图指向包缓冲内部（偏移 = HEADER_LEN=18），而非新分配
        assert_eq!(h.payload.as_ptr() as usize - p.as_ptr() as usize, HEADER_LEN);
    }

    #[test]
    fn truncated_is_err() {
        let p = build_packet(1, 2, 3, b"abcdef");
        assert_eq!(parse_packet(&p[..HEADER_LEN + 2]).err(), Some(HeaderErr::Truncated));
        assert_eq!(parse_packet(&p[..8]).err(), Some(HeaderErr::Truncated));
    }

    #[test]
    fn bad_magic_is_err() {
        let mut p = build_packet(1, 2, 3, b"x");
        p[0] = b'X';
        assert_eq!(parse_packet(&p).err(), Some(HeaderErr::BadMagic));
    }
}
