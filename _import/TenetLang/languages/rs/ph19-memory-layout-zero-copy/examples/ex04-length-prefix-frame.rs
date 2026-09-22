// examples/ex04-length-prefix-frame.rs —— length-prefix framing：长度检查 + 流式增量解析
// 对应主文档 3.7。演示两种形态：①单次解析一帧（借用的 payload 视图，零拷贝）——
// ②流式 Reader（网络分块到达）——头部校验（长度上限）、半帧等待、解析后压缩缓冲。
// 安全纪律要点：长度字段来自不可信字节 —— 先校验再相信，任何「按长度分配/切分」都要先过上限闸门。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行：
//   rustc --edition 2021 -D warnings ex04-length-prefix-frame.rs -o /tmp/ph19-ex04 && /tmp/ph19-ex04
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。
use std::fmt;

/// 帧格式：[payload_len: u32 BE][payload]。len 是「长度前缀」，让接收方先知道载荷多大。
/// 帧头固定 4 字节 —— 但「长度前缀 + 上限」是关键：任何协议都要回答「我能信这个长度吗」。
const MAX_FRAME: usize = 1 << 20; // 单帧上限 1 MiB：防内存耗尽的 DoS 闸门

/// 解析一帧（buffer 恰好含一帧）。payload 是借用输入的子切片 —— 没有分配、没有复制。
fn parse_frame<'a>(buf: &'a [u8]) -> Result<Frame<'a>, FrameErr> {
    let len_bytes: [u8; 4] = buf.get(..4).ok_or(FrameErr::Truncated)?.try_into().map_err(|_| FrameErr::Truncated)?;
    let payload_len = u32::from_be_bytes(len_bytes) as usize;
    if payload_len > MAX_FRAME {
        return Err(FrameErr::TooLarge(payload_len));
    }
    let payload = buf
        .get(4..4 + payload_len)
        .ok_or(FrameErr::Truncated)?;
    Ok(Frame { payload })
}

#[derive(PartialEq, Eq)]
struct Frame<'a> {
    payload: &'a [u8],
}

/// 流式帧接收器：网络包分块到达，先积累、再按帧头判定是否凑齐一帧。
struct FrameReader {
    pending: Vec<u8>, // 已收到但尚未组成完整帧的字节
    consumed: usize,  // pending 里已被上一帧用掉的前缀长度
}

impl FrameReader {
    fn new() -> Self {
        FrameReader { pending: Vec::new(), consumed: 0 }
    }

    /// 追加一段网络到达的字节
    fn feed(&mut self, chunk: &[u8]) {
        self.pending.extend_from_slice(chunk);
    }

    /// 若凑齐完整一帧则返回之（借用 pending；返回后调用 compact 释放已用前缀）。
    /// 这是「半帧等待 + 长度校验」的核心：缺字节返回 Ok(None)，非法长度返回 Err。
    fn next_frame(&mut self) -> Result<Option<Frame<'_>>, FrameErr> {
        let avail = &self.pending[self.consumed..];
        if avail.len() < 4 {
            return Ok(None); // 连帧头都没凑齐
        }
        let len_bytes: [u8; 4] = avail[..4].try_into().expect("已保证 ≥4 字节");
        let payload_len = u32::from_be_bytes(len_bytes) as usize;
        if payload_len > MAX_FRAME {
            return Err(FrameErr::TooLarge(payload_len));
        }
        let total = 4 + payload_len;
        if avail.len() < total {
            return Ok(None); // 帧头已到，载荷还没到齐 —— 等下一块
        }
        let payload = &avail[4..total];
        self.consumed += total; // 标记：这一帧已交付
        Ok(Some(Frame { payload }))
    }

    /// 把已消费的前缀移出 pending（用 drain 前移余下字节；工程上更多用 bytes::Bytes 免搬运，见 3.5）
    fn compact(&mut self) {
        if self.consumed > 0 {
            self.pending.drain(..self.consumed);
            self.consumed = 0;
        }
    }
}

impl fmt::Debug for Frame<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Frame{{payload({}B) = {:02X?}}}", self.payload.len(), self.payload)
    }
}

#[derive(Debug)]
enum FrameErr {
    /// 缓冲不足一帧/一个帧头
    Truncated,
    /// 长度前缀超过上限（把「长度」当真相之前先过闸）
    TooLarge(usize),
}

impl fmt::Display for FrameErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FrameErr::Truncated => write!(f, "帧数据不足（截断）"),
            FrameErr::TooLarge(n) => write!(f, "长度前缀 {n} 超过上限 {MAX_FRAME} 字节（拒绝）"),
        }
    }
}

fn main() {
    // —— 1. 单帧解析：构造一帧字节 → 零拷贝取出 payload ——
    println!("== 单帧解析 ==");
    let body: Vec<u8> = (0x10..0x18).collect();
    let mut single = Vec::new();
    single.extend_from_slice(&(body.len() as u32).to_be_bytes());
    single.extend_from_slice(&body);
    let frame = parse_frame(&single).expect("合法帧");
    println!("{frame:?}");
    println!("payload 起始偏移 = 4（恰好在长度字段之后），借用输入、无新分配");

    // —— 2. 长度不足与超上限：两条错误路径 ——
    println!();
    println!("== 非法输入被拒 ==");
    let truncated = &single[..5]; // 声称 8 字节却只给 1 字节载荷
    println!("截断帧       → {:?}", parse_frame(truncated).err().expect("应报错").to_string());
    let mut evil = Vec::new();
    evil.extend_from_slice(&0xFFFF_FFFFu32.to_be_bytes()); // 伪造 4 GiB 长度
    println!("伪造 4GiB 帧 → {:?}", parse_frame(&evil).err().expect("应报错").to_string());

    // —— 3. 流式 Reader：三块到达拼成一帧 ——
    println!();
    println!("== 流式增量解析 ==");
    let mut reader = FrameReader::new();
    reader.feed(&single[..4]); // 第 1 块：恰好只有帧头
    println!("只到帧头：next_frame = {:?}", reader.next_frame().map(|f| f.is_none()));
    reader.feed(&single[4..]); // 第 2 块：补齐载荷
    let f = reader.next_frame().expect("合法帧").expect("应凑齐一帧");
    println!("补齐后  ：{f:?}");
    reader.compact();
    println!("compact 后待处理字节 = {}（已消费前缀被清掉）", reader.pending.len());

    // —— 4. 两帧粘连（同一个 TCP 流里多帧连续到达）——逐帧吐出 ——
    println!();
    println!("== 粘连多帧逐个吐出 ==");
    let body2: Vec<u8> = (0xA0..0xA4).collect();
    let mut stream = Vec::new();
    stream.extend_from_slice(&(body.len() as u32).to_be_bytes());
    stream.extend_from_slice(&body);
    stream.extend_from_slice(&(body2.len() as u32).to_be_bytes());
    stream.extend_from_slice(&body2);
    let mut reader2 = FrameReader::new();
    reader2.feed(&stream[..3]); // 前 3 字节：连帧头都没齐
    reader2.feed(&stream[3..]); // 其余一次到齐（含两整帧）
    let mut got = Vec::new();
    while let Some(fr) = reader2.next_frame().expect("流合法") {
        got.push(fr.payload.len());
        reader2.compact();
    }
    println!("粘连流解析出帧载荷长度 = {got:?}（第 1 块 3 字节被等待吸收）");

    // —— 安全收尾：anti-pattern 备忘（只讲不写）——
    // ⚠️ 不要写成：let n = read_u32(); Vec::with_capacity(n) —— 先 validate(n <= MAX) 再 allocate，
    //    否则恶意长度直接打穿内存。上限、半帧等待、TryInto 三件套是 length-prefix 协议的出厂配置。
}
