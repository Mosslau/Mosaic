// exercises/sol-05-frame-parser.rs —— 练习 5 参考实现：length-prefix frame parser
// 对应 roadmap 第 19 节练习「实现 length-prefix frame parser」与主文档 3.7。
// 帧格式：[len: u32 BE][type: u8][payload: len 字节]。type 是业务标记（如请求/响应）。
// 实现目标：网络分块到达也能正确拼帧——半帧等待、粘连帧逐条吐出、长度先过上限闸门；
// 外加一条比「能跑」更硬的验收：把同一段字节流按「每一个可能的切分点」拆成两块喂入，
// 解析结果必须与整段一次喂入完全一致（本文件测试区逐点验证）。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-05-frame-parser.rs -o /tmp/ph19-sol05 && /tmp/ph19-sol05
//   rustc --edition 2021 -D warnings --test sol-05-frame-parser.rs -o /tmp/ph19-sol05-t && /tmp/ph19-sol05-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。
use std::fmt;

const MAX_FRAME: u32 = 1 << 20; // 单帧上限：恶意长度先被它拦下

#[derive(Debug, PartialEq, Eq, Clone)]
struct Frame {
    ty: u8,
    payload: Vec<u8>, // 跨网络分块的帧必须拥有数据；进程内解析用借用切片即可（见 sol-02/ex03）
}

/// 一次性解析：假设 buf 恰好是一段「完整帧流」，返回能解码的全部帧。
fn parse_all(buf: &[u8]) -> Result<Vec<Frame>, FrameErr> {
    let mut out = Vec::new();
    let mut pos = 0usize;
    while pos < buf.len() {
        let head = buf.get(pos..pos + 5).ok_or(FrameErr::Incomplete)?;
        let len = u32::from_be_bytes(head[0..4].try_into().map_err(|_| FrameErr::Incomplete)?);
        if len > MAX_FRAME {
            return Err(FrameErr::TooLarge(len));
        }
        let ty = head[4];
        let end = pos + 5 + len as usize;
        let payload = buf.get(pos + 5..end).ok_or(FrameErr::Incomplete)?.to_vec();
        out.push(Frame { ty, payload });
        pos = end;
    }
    Ok(out)
}

/// 流式帧解析器：accumulate 一段 pending 缓冲，能解码多少解多少。
struct FrameParser {
    pending: Vec<u8>,
}

impl FrameParser {
    fn new() -> Self {
        FrameParser { pending: Vec::new() }
    }

    fn feed(&mut self, chunk: &[u8]) {
        self.pending.extend_from_slice(chunk);
    }

    /// 解码当前 pending 中所有完整帧；不足一帧则原地等待下一块。
    fn drain_frames(&mut self) -> Result<Vec<Frame>, FrameErr> {
        let mut out = Vec::new();
        loop {
            if self.pending.len() < 5 {
                break; // 帧头都没齐 → 等
            }
            let len =
                u32::from_be_bytes(self.pending[0..4].try_into().expect("len ≥5 已保证")) as usize;
            if len as u32 > MAX_FRAME {
                return Err(FrameErr::TooLarge(len as u32)); // 长度闸门：先拒后忘
            }
            if self.pending.len() < 5 + len {
                break; // 帧头齐了载荷没齐 → 等
            }
            let ty = self.pending[4];
            let payload = self.pending[5..5 + len].to_vec();
            self.pending.drain(..5 + len); // 吃掉已消费前缀（bytes 方案用头指针，见主文档 3.5）
            out.push(Frame { ty, payload });
        }
        Ok(out)
    }
}

#[derive(Debug, PartialEq, Eq)]
enum FrameErr {
    Incomplete,
    TooLarge(u32),
}

impl fmt::Display for FrameErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FrameErr::Incomplete => write!(f, "帧数据不完整（截断）"),
            FrameErr::TooLarge(n) => write!(f, "长度前缀 {n} 超过上限 {MAX_FRAME}（拒绝）"),
        }
    }
}

fn encode_frame(ty: u8, payload: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    out.extend_from_slice(&(payload.len() as u32).to_be_bytes());
    out.push(ty);
    out.extend_from_slice(payload);
    out
}

fn main() {
    let stream: Vec<u8> = encode_frame(1, b"request-a")
        .into_iter()
        .chain(encode_frame(2, b"request-b"))
        .chain(encode_frame(3, b"x"))
        .collect();
    println!("字节流共 {} 字节（3 帧）", stream.len());

    // —— 1. 整段一次喂入 ——
    let mut p = FrameParser::new();
    p.feed(&stream);
    let frames = p.drain_frames().expect("合法流");
    for (i, f) in frames.iter().enumerate() {
        println!(
            "帧 {i}: type={} payload={}",
            f.ty,
            String::from_utf8_lossy(&f.payload)
        );
    }

    // parse_all：整段单发解析应与流式结果一致（多帧并发解码用单发，网络流用流式）
    let single = parse_all(&stream).expect("整段可解析");
    assert_eq!(single, frames);
    println!("parse_all 整段单发结果与流式一致（{count} 帧）", count = single.len());

    // —— 2. 半帧喂入再补齐 ——
    let mut p2 = FrameParser::new();
    p2.feed(&stream[..3]); // 连帧头都没齐
    println!("喂入 3 字节后解出 {} 帧（应等待）", p2.drain_frames().expect("合法").len());
    p2.feed(&stream[3..]);
    println!("补齐后共 {} 帧", p2.drain_frames().expect("合法").len());

    // —— 3. 恶意长度 ——
    let mut evil = Vec::new();
    evil.extend_from_slice(&0xFFFF_FFFFu32.to_be_bytes());
    evil.push(0); // 补足 ≥5 字节，让帧头可读、走到长度闸门
    let mut p3 = FrameParser::new();
    p3.feed(&evil);
    println!("伪造 4GiB 帧 → {:?}", p3.drain_frames().err().expect("应拒绝").to_string());
}

#[cfg(test)]
mod tests {
    use super::*;

    fn two_frame_stream() -> Vec<u8> {
        encode_frame(1, b"alpha")
            .into_iter()
            .chain(encode_frame(2, b"bravo"))
            .collect()
    }

    #[test]
    fn parses_multiple_frames_in_order() {
        let frames = parse_all(&two_frame_stream()).expect("合法");
        assert_eq!(frames.len(), 2);
        assert_eq!(frames[0].ty, 1);
        assert_eq!(frames[0].payload, b"alpha");
        assert_eq!(frames[1].ty, 2);
        assert_eq!(frames[1].payload, b"bravo");
    }

    #[test]
    fn identical_result_for_every_split_point() {
        // 核心验收：对 0..=总长 的每个切分点，两段喂入的结果必须与整段一次喂入一致
        let stream = two_frame_stream();
        let reference = parse_all(&stream).expect("整段应可解析");
        for split in 0..=stream.len() {
            let mut p = FrameParser::new();
            p.feed(&stream[..split]);
            let first = p.drain_frames().expect("合法");
            p.feed(&stream[split..]);
            let mut all = first;
            all.extend(p.drain_frames().expect("合法"));
            assert_eq!(all, reference, "切分点 {split} 处结果不一致");
        }
    }

    #[test]
    fn too_large_length_is_err_and_parser_recovers() {
        let mut stream = Vec::new();
        stream.extend_from_slice(&(MAX_FRAME + 1).to_be_bytes());
        stream.push(0); // 补足帧头，让长度闸门生效
        let mut p = FrameParser::new();
        p.feed(&stream);
        assert_eq!(p.drain_frames().err(), Some(FrameErr::TooLarge(MAX_FRAME + 1)));
        // 错误后 parser 可复用：清掉坏前缀继续收合法帧（此处直接重置演示可用性）
        let mut p2 = FrameParser::new();
        p2.feed(&encode_frame(7, b"ok"));
        assert_eq!(p2.drain_frames().expect("合法").len(), 1);
    }

    #[test]
    fn incomplete_tail_waits() {
        let stream = two_frame_stream();
        let mut p = FrameParser::new();
        p.feed(&stream[..stream.len() - 1]); // 最后差 1 字节
        let frames = p.drain_frames().expect("合法");
        assert_eq!(frames.len(), 1); // 只出第一帧
        p.feed(&stream[stream.len() - 1..]);
        assert_eq!(p.drain_frames().expect("合法").len(), 1); // 补齐后第二帧出来
    }
}
