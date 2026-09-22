// exercises/sol-03-wal-record.rs —— 练习 3 参考实现：解析 WAL record（分片类型 + checksum + 零拷贝边界）
// 对应 roadmap 第 19 节练习「解析 WAL record」与主文档 3.8。
// 格式规范（教学简化，字段小端）：沿用 LevelDB log record 的 7B 头部骨架——
//   [checksum: u32][length: u16][type: u8][payload: length 字节]
//   type: 1=FULL, 2=FIRST, 3=MIDDLE, 4=LAST
// checksum 直接对 payload 求 crc32c（简化：LevelDB 原文还覆盖 type 并做 mask，见注释）。
// 零拷贝边界是本题教学重点：FULL 记录可直接借用 payload（Cow::Borrowed）；
// 一条逻辑记录被 FIRST/MIDDLE/LAST 切成多段时，段与段之间隔着各段的头部，
// 无法表示成连续切片 → 只能拼进 Vec（Cow::Owned）——「该复制时才复制」本身就是零拷贝心智的一部分。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-03-wal-record.rs -o /tmp/ph19-sol03 && /tmp/ph19-sol03
//   rustc --edition 2021 -D warnings --test sol-03-wal-record.rs -o /tmp/ph19-sol03-t && /tmp/ph19-sol03-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。
use std::borrow::Cow;
use std::fmt;

const TYPE_FULL: u8 = 1;
const TYPE_FIRST: u8 = 2;
const TYPE_MIDDLE: u8 = 3;
const TYPE_LAST: u8 = 4;
const HEADER_LEN: usize = 7;
/// 单条物理 record 的 payload ≤ 65535（length 是 u16）；
/// 另设逻辑记录总长上限，防止用「无限分片链」打穿内存（3.7 长度闸门的延伸）。
const MAX_LOGICAL: usize = 1 << 20;

/// 解析结果：一条「逻辑记录」的载荷。Borrowed = FULL 直借输入；Owned = 跨段拼装。
struct LogItem<'a> {
    fragmented: bool,
    payload: Cow<'a, [u8]>,
}

/// 顺序扫描整段 WAL 缓冲，输出全部完整逻辑记录。
fn parse_log<'a>(buf: &'a [u8]) -> Result<Vec<LogItem<'a>>, LogErr> {
    let mut items = Vec::new();
    let mut pos = 0usize;
    // 跨段拼装的「半成品」只可能是 Owned（见文件头零拷贝边界说明）
    let mut pending: Option<Vec<u8>> = None;
    let mut pending_len = 0usize;

    while pos < buf.len() {
        let head = buf.get(pos..pos + HEADER_LEN).ok_or(LogErr::Truncated)?;
        let expect_crc = u32::from_le_bytes(head[0..4].try_into().map_err(|_| LogErr::Truncated)?);
        let length = u16::from_le_bytes(head[4..6].try_into().map_err(|_| LogErr::Truncated)?) as usize;
        let rtype = head[6];
        let payload = buf.get(pos + HEADER_LEN..pos + HEADER_LEN + length).ok_or(LogErr::Truncated)?;
        if crc32c(payload) != expect_crc {
            return Err(LogErr::ChecksumMismatch { expect: expect_crc });
        }

        match rtype {
            TYPE_FULL => {
                if pending.is_some() {
                    return Err(LogErr::Protocol("FULL 出现在未收尾的分片链中途"));
                }
                items.push(LogItem { fragmented: false, payload: Cow::Borrowed(payload) });
            }
            TYPE_FIRST => {
                if pending.is_some() {
                    return Err(LogErr::Protocol("FIRST 出现在未收尾的分片链中途"));
                }
                pending = Some(payload.to_vec()); // 分片跨段，必须 Owned
                pending_len = payload.len();
                if pending_len > MAX_LOGICAL {
                    return Err(LogErr::TooLarge(pending_len));
                }
            }
            TYPE_MIDDLE => {
                let acc = pending.as_mut().ok_or(LogErr::Protocol("MIDDLE 前无 FIRST"))?;
                if pending_len + payload.len() > MAX_LOGICAL {
                    return Err(LogErr::TooLarge(pending_len + payload.len()));
                }
                pending_len += payload.len();
                acc.extend_from_slice(payload);
            }
            TYPE_LAST => {
                let acc = pending.as_mut().ok_or(LogErr::Protocol("LAST 前无 FIRST"))?;
                if pending_len + payload.len() > MAX_LOGICAL {
                    return Err(LogErr::TooLarge(pending_len + payload.len()));
                }
                pending_len += payload.len();
                acc.extend_from_slice(payload);
                items.push(LogItem {
                    fragmented: true,
                    payload: Cow::Owned(pending.take().expect("pending 已确认存在")),
                });
            }
            other => return Err(LogErr::UnknownType(other)),
        }
        pos += HEADER_LEN + length;
    }
    if pending.is_some() {
        return Err(LogErr::Protocol("分片链未以 LAST 收尾（日志尾部截断）"));
    }
    Ok(items)
}

/// 手写 crc32c（Castagnoli，教学逐位版）；工程请用 crc32c/crc32fast。
/// ⚠️ 教学简化 1：checksum 只覆盖 payload（LevelDB 原文覆盖 type+payload 并做 mask）。
fn crc32c(bytes: &[u8]) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    for &b in bytes {
        crc ^= b as u32;
        for _ in 0..8 {
            let mask = (crc & 1).wrapping_neg();
            crc = (crc >> 1) ^ (0x82F6_3B78 & mask);
        }
    }
    crc ^ 0xFFFF_FFFF
}

#[derive(Debug, PartialEq, Eq)]
enum LogErr {
    Truncated,
    ChecksumMismatch { expect: u32 },
    UnknownType(u8),
    TooLarge(usize),
    Protocol(&'static str),
}

impl fmt::Display for LogErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            LogErr::Truncated => write!(f, "缓冲截断（头部或 payload 不足）"),
            LogErr::ChecksumMismatch { expect } => write!(f, "CRC 校验失败（期望 0x{expect:08X}）"),
            LogErr::UnknownType(t) => write!(f, "未知记录类型 {t}"),
            LogErr::TooLarge(n) => write!(f, "逻辑记录长度 {n} 超过上限 {MAX_LOGICAL}"),
            LogErr::Protocol(msg) => write!(f, "协议错误：{msg}"),
        }
    }
}

/// 编码一条物理 record 并追加进 log（教学编码器，字段与解析器镜像）。
fn append_physical(log: &mut Vec<u8>, rtype: u8, payload: &[u8]) {
    log.extend_from_slice(&crc32c(payload).to_le_bytes());
    log.extend_from_slice(&(payload.len() as u16).to_le_bytes());
    log.push(rtype);
    log.extend_from_slice(payload);
}

fn main() {
    // —— 0. crc32c 自检（Castagnoli 标准向量）——
    assert_eq!(crc32c(b"123456789"), 0xE306_9283, "crc32c 实现偏离标准向量");
    println!("crc32c 自检通过");

    // —— 1. 组装日志：一条 FULL + 一条切成 FIRST/MIDDLE/LAST 的逻辑记录 ——
    println!();
    println!("== 组装 WAL 并解析 ==");
    let mut log = Vec::new();
    append_physical(&mut log, TYPE_FULL, b"key=temperature value=36.5"); // 借用可
    append_physical(&mut log, TYPE_FIRST, b"key=humidity val");
    append_physical(&mut log, TYPE_MIDDLE, b"ue=60 (split ");
    append_physical(&mut log, TYPE_LAST, b"across 4B)"); // 跨段必须拼装
    println!("日志共 {} 字节", log.len());

    for (i, item) in parse_log(&log).expect("合法日志").iter().enumerate() {
        println!(
            "第 {i} 条：{} payload={}",
            if item.fragmented {
                "分片链 Owned（跨段拼装，唯一需要复制的情形）"
            } else {
                "FULL Borrowed（零拷贝直借）"
            },
            String::from_utf8_lossy(&item.payload)
        );
    }

    // —— 2. 篡改一个字节 → checksum 拦截 ——
    println!();
    println!("== 校验 ==");
    let mut tampered = log.clone();
    tampered[HEADER_LEN + 3] ^= 0x01;
    match parse_log(&tampered) {
        Ok(_) => println!("意外通过"),
        Err(e) => println!("篡改日志 → {e}"),
    }

    // —— 3. 截断/协议错误路径 ——
    println!();
    println!("== 错误路径 ==");
    let cut = &log[..log.len() - 3]; // 尾部被砍：LAST 的 payload 不完整
    println!("尾截断   → {:?}", parse_log(cut).err().expect("应失败").to_string());
    let mut unclosed = Vec::new();
    append_physical(&mut unclosed, TYPE_FIRST, b"no end");
    println!("未收尾链 → {:?}", parse_log(&unclosed).err().expect("应失败").to_string());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc32c_matches_standard_vector() {
        assert_eq!(crc32c(b"123456789"), 0xE306_9283);
        assert_eq!(crc32c(b""), 0);
    }

    #[test]
    fn full_record_is_borrowed() {
        let mut log = Vec::new();
        append_physical(&mut log, TYPE_FULL, b"abc");
        let items = parse_log(&log).expect("合法");
        assert_eq!(items.len(), 1);
        assert!(!items[0].fragmented);
        assert!(matches!(items[0].payload, Cow::Borrowed(_)));
        assert_eq!(items[0].payload.as_ref(), b"abc");
    }

    #[test]
    fn fragmented_record_is_owned_and_concatenated() {
        let mut log = Vec::new();
        append_physical(&mut log, TYPE_FIRST, b"ab");
        append_physical(&mut log, TYPE_MIDDLE, b"cd");
        append_physical(&mut log, TYPE_LAST, b"ef");
        let items = parse_log(&log).expect("合法");
        assert_eq!(items.len(), 1);
        assert!(matches!(items[0].payload, Cow::Owned(_)));
        assert_eq!(items[0].payload.as_ref(), b"abcdef");
    }

    #[test]
    fn mixed_log_preserves_order() {
        let mut log = Vec::new();
        append_physical(&mut log, TYPE_FULL, b"one");
        append_physical(&mut log, TYPE_FIRST, b"tw");
        append_physical(&mut log, TYPE_LAST, b"o");
        append_physical(&mut log, TYPE_FULL, b"three");
        let items = parse_log(&log).expect("合法");
        let all: Vec<&[u8]> = items.iter().map(|i| i.payload.as_ref()).collect();
        assert_eq!(all, [&b"one"[..], &b"two"[..], &b"three"[..]]);
    }

    #[test]
    fn checksum_mismatch_is_err() {
        let mut log = Vec::new();
        append_physical(&mut log, TYPE_FULL, b"abc");
        log[HEADER_LEN] ^= 0x01;
        assert!(matches!(parse_log(&log), Err(LogErr::ChecksumMismatch { .. })));
    }

    #[test]
    fn protocol_violations_are_err() {
        // MIDDLE 前无 FIRST
        let mut log = Vec::new();
        append_physical(&mut log, TYPE_MIDDLE, b"x");
        assert!(parse_log(&log).is_err());
        // FIRST 后接 FULL
        let mut log2 = Vec::new();
        append_physical(&mut log2, TYPE_FIRST, b"x");
        append_physical(&mut log2, TYPE_FULL, b"y");
        assert!(parse_log(&log2).is_err());
        // 链未收尾
        let mut log3 = Vec::new();
        append_physical(&mut log3, TYPE_FIRST, b"x");
        assert!(parse_log(&log3).is_err());
    }

    #[test]
    fn truncated_header_or_payload_is_err() {
        let mut log = Vec::new();
        append_physical(&mut log, TYPE_FULL, b"hello");
        assert!(parse_log(&log[..HEADER_LEN + 2]).is_err());
        assert!(parse_log(&log[..HEADER_LEN - 1]).is_err());
    }
}
