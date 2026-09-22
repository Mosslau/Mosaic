// examples/crates/src/bin/ex07-nom-parser.rs —— nom 8 组合子解析器：小解析器串成大树
// 对应主文档 3.6/4.4。演示：tag/take/be_u16/be_u32 等基础组合子、逐层串出 record 解析器、
// 外层 length 信封 + 内层 record 的嵌套组合、输入不足/非法长度的错误与剩余输出、
// 以及「解析函数不拥有输入」→ 零拷贝切片照常成立（nom 天然工作在 &[u8] 借用上）。
// ⚠️ nom 8.0 对 tag 的参数要求切片（tag(&b".."[..]) 而非 tag(b"..")），写法与 nom 7 略有差异。
// 验证环境：cargo 1.92.0，依赖 nom 8.0.0（已在 Cargo.toml 锁定）。构建/运行/测试：
//   cd examples/crates
//   CARGO_TARGET_DIR=/tmp/ph19-target cargo run --bin ex07-nom-parser
//   CARGO_TARGET_DIR=/tmp/ph19-target cargo test --bin ex07-nom-parser
// 验证状态：已验证（cargo 1.92.0 / nom 8.0.0，aarch64-apple-darwin）。
use nom::bytes::complete::{tag, take};
use nom::IResult;

/// 一条 KV 消息（内部格式，借用输入，零拷贝）：
///   [magic: "KV" 2B][ty: u16 BE][seq: u32 BE][klen: u32 BE][key][vlen: u32 BE][value]
#[derive(Debug, PartialEq, Eq)]
struct Msg<'a> {
    ty: u16,
    seq: u32,
    key: &'a [u8],
    value: &'a [u8],
}

fn be_u16(i: &[u8]) -> IResult<&[u8], u16> {
    let (rest, bytes) = take(2usize)(i)?;
    Ok((
        rest,
        u16::from_be_bytes(bytes.try_into().expect("take(2) 已保证 2 字节")),
    ))
}

fn be_u32(i: &[u8]) -> IResult<&[u8], u32> {
    let (rest, bytes) = take(4usize)(i)?;
    Ok((
        rest,
        u32::from_be_bytes(bytes.try_into().expect("take(4) 已保证 4 字节")),
    ))
}

/// 逐层组合：magic → ty → seq → key → value。每一步都是独立可测的小组合子。
fn parse_msg(i: &[u8]) -> IResult<&[u8], Msg<'_>> {
    let (i, _) = tag(&b"KV"[..])(i)?; // 魔数校验
    let (i, ty) = be_u16(i)?;
    let (i, seq) = be_u32(i)?;
    let (i, klen) = be_u32(i)?;
    let (i, key) = take(klen)(i)?; // 按长度字段切出 key 子切片
    let (i, vlen) = be_u32(i)?;
    let (i, value) = take(vlen)(i)?;
    Ok((
        i,
        Msg {
            ty,
            seq,
            key,
            value,
        },
    ))
}

/// 外层「长度信封」：[len: u32 BE][内层完整消息]。length-prefix framing + 内层组合解析器。
fn parse_envelope(i: &[u8]) -> IResult<&[u8], Msg<'_>> {
    let (i, len) = be_u32(i)?;
    let (i, payload) = take(len)(i)?; // 先按长度圈定内层区域
    let (_consumed_all, msg) = parse_msg(payload)?; // 内层完整消费
    Ok((i, msg))
}

fn main() {
    // —— 1. 组一段 record 并解析 ——
    println!("== parse_msg：组合子逐层解析 ==");
    let mut raw = Vec::new();
    raw.extend_from_slice(b"KV");
    raw.extend_from_slice(&0x0001u16.to_be_bytes()); // ty=1
    raw.extend_from_slice(&100_001u32.to_be_bytes()); // seq
    raw.extend_from_slice(&(b"temperature".len() as u32).to_be_bytes());
    raw.extend_from_slice(b"temperature");
    raw.extend_from_slice(&(b"36.5".len() as u32).to_be_bytes());
    raw.extend_from_slice(b"36.5");
    match parse_msg(&raw) {
        Ok((rest, msg)) => println!("解析成功：{msg:?}，剩余 {} 字节", rest.len()),
        Err(e) => println!("解析失败：{e:?}"),
    }
    // 实测输出：解析成功：Msg { ty: 1, seq: 100001, key: b"temperature", value: b"36.5" }，剩余 0 字节

    // —— 2. 长度信封：len 前缀 + 内部 record ——
    println!();
    println!("== parse_envelope：外层长度 + 内层 record ==");
    let mut enveloped = Vec::new();
    enveloped.extend_from_slice(&(raw.len() as u32).to_be_bytes()); // 外层 [len]
    enveloped.extend_from_slice(&raw);
    match parse_envelope(&enveloped) {
        Ok((rest, msg)) => println!(
            "信封解析成功：seq={} key={:?}，剩余 {} 字节",
            msg.seq,
            msg.key,
            rest.len()
        ),
        Err(e) => println!("信封解析失败：{e:?}"),
    }

    // —— 3. 错误路径：截断 → complete 族组合子返回 Err，剩余输入可定位 ——
    println!();
    println!("== 输入不足 ==");
    let cut = &raw[..12]; // 砍在 key 区中间
    match parse_msg(cut) {
        Ok(_) => println!("意外成功"),
        Err(_) => println!("截断输入 → nom 返回 Err（key 区读到一半时输入已耗尽），调用方据此判定“差数据、等下一块”"),
    }

    // —— 4. complete vs streaming：同一 take，两种终止语义 ——
    println!();
    println!("== complete vs streaming（输入不足时的差异）==");
    // complete::take 输入不足 → 直接 Err（Error），语义「这段输入不完整就判定失败」
    let r: IResult<&[u8], &[u8]> = nom::bytes::complete::take(5usize)(b"ab");
    println!("complete::take(5) on 2B → {r:?}");
    // streaming::take 输入不足 → Err(Incomplete(Needed))，语义「告诉流式调用方还差几个字节」
    let r2: IResult<&[u8], &[u8]> = nom::bytes::streaming::take(5usize)(b"ab");
    println!("streaming::take(5) on 2B → {r2:?}");
    // 实测输出：
    //   complete::take(5) on 2B → Err(Error(Error { input: [97, 98], code: Eof }))
    //   streaming::take(5) on 2B → Err(Incomplete(Size(3)))
    // 全量已知缓冲（读文件/一次读满 socket）用 complete；边收边解析（TCP 流）用 streaming，
    // 后者把「还差 3 字节」直接编码进类型 —— 与 3.7 的半帧等待是同一个思路的库化表达。

    // —— 5. 组合解析器复用于流内多个 record ——
    println!();
    println!("== 两个 record 连排，循环消费 ==");
    let mut log = Vec::new();
    log.extend_from_slice(&raw);
    log.extend_from_slice(&raw);
    let mut pos = 0usize;
    let mut n = 0;
    while pos < log.len() {
        match parse_msg(&log[pos..]) {
            Ok((rest, msg)) => {
                n += 1;
                println!(
                    "record #{n}: seq={} key={} value={}",
                    msg.seq,
                    String::from_utf8_lossy(msg.key),
                    String::from_utf8_lossy(msg.value)
                );
                pos = log.len() - rest.len(); // 前进到未消费处（rest 是切片，用长度换算下标）
            }
            Err(e) => {
                // 打印失败点还剩余多少未消费字节（定位「坏在第几个 record / 哪段数据」）
                let leftover = match e {
                    nom::Err::Error(err) => err.input.len(),
                    nom::Err::Failure(err) => err.input.len(),
                    nom::Err::Incomplete(_) => 0,
                };
                let idx = n + 1;
                println!("record #{idx} 解析失败（截断/坏数据），失败点剩余 {leftover} 字节");
                break;
            }
        }
    }
    println!("共消费 {n} 条完整 record");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build_msg(ty: u16, seq: u32, key: &[u8], value: &[u8]) -> Vec<u8> {
        let mut raw = Vec::new();
        raw.extend_from_slice(b"KV");
        raw.extend_from_slice(&ty.to_be_bytes());
        raw.extend_from_slice(&seq.to_be_bytes());
        raw.extend_from_slice(&(key.len() as u32).to_be_bytes());
        raw.extend_from_slice(key);
        raw.extend_from_slice(&(value.len() as u32).to_be_bytes());
        raw.extend_from_slice(value);
        raw
    }

    #[test]
    fn msg_roundtrip() {
        let raw = build_msg(7, 42, b"k", b"v");
        let (rest, msg) = parse_msg(&raw).expect("合法 record");
        assert!(rest.is_empty());
        assert_eq!(
            msg,
            Msg {
                ty: 7,
                seq: 42,
                key: &b"k"[..],
                value: &b"v"[..]
            }
        );
    }

    #[test]
    fn envelope_roundtrip() {
        let raw = build_msg(1, 100_001, b"temperature", b"36.5");
        let mut enveloped = Vec::new();
        enveloped.extend_from_slice(&(raw.len() as u32).to_be_bytes());
        enveloped.extend_from_slice(&raw);
        let (rest, msg) = parse_envelope(&enveloped).expect("合法信封");
        assert!(rest.is_empty());
        assert_eq!(msg.key, &b"temperature"[..]);
        assert_eq!(msg.value, &b"36.5"[..]);
    }

    #[test]
    fn truncated_input_is_error() {
        let raw = build_msg(3, 9, b"longer-key", b"longer-value");
        assert!(parse_msg(&raw[..10]).is_err()); // 砍在 key 区中间
    }

    #[test]
    fn bad_magic_is_error() {
        let raw = build_msg(3, 9, b"k", b"v");
        let mut bad = raw;
        bad[0] = b'X';
        assert!(parse_msg(&bad).is_err());
    }
}
