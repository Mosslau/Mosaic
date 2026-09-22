// examples/ex03-slice-zero-copy.rs —— slice 与 buffer：用 &[u8] 借用缓冲、切分、返回借用数据
// 对应主文档 3.4/4.2。演示：Vec → &[u8] 零成本、切分产生「指向原缓冲内部」的子切片
// （指针算术证明没有复制）、函数返回借用输入数据的子切片（呼应 ph18：先修好借用，这里让它省钱）、
// chunks / chunks_exact 的差异与 remainder 处理。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行：
//   rustc --edition 2021 -D warnings ex03-slice-zero-copy.rs -o /tmp/ph19-ex03 && /tmp/ph19-ex03
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。
use std::mem::size_of;

/// 从缓冲里切出 payload 区：返回的子切片「借用」buf，不产生任何拷贝。
/// 输入是网络/文件缓冲，输出直接指向它内部 —— 这就是零拷贝的核心动作（兑现 ph18 的预告）。
fn payload_of<'a>(buf: &'a [u8]) -> Option<&'a [u8]> {
    // 头部布局：flags(1B) + type(2B BE) + payload_len(2B BE) = 5 字节头
    const HEADER: usize = 1 + 2 + 2;
    let whole = buf.get(..HEADER)?;
    let payload_len = u16::from_be_bytes(whole[3..5].try_into().ok()?) as usize;
    let payload = buf.get(HEADER..HEADER + payload_len)?; // 长度检查：不足返回 None
    Some(payload)
}

/// 返回借用输入首尾字段的「视图」：元组同样携带生命周期（都是输入的子区间）
fn head_and_tail<'a>(buf: &'a [u8]) -> Option<(&'a [u8], &'a [u8])> {
    let hdr = buf.get(0..2)?;
    let tail = buf.get(buf.len().checked_sub(2)?..)?;
    Some((hdr, tail))
}

fn main() {
    // —— 1. 零成本转换：Vec 与切片共享同一块堆内存 ——
    println!("== Vec → &[u8] 零成本 ==");
    println!("size_of::<Vec<u8>>() = {} 字节（ptr+len+cap 三元组）", size_of::<Vec<u8>>());
    println!("size_of::<&[u8]>()   = {} 字节（ptr+len 胖指针）", size_of::<&[u8]>());
    println!("size_of::<&str>()    = {} 字节", size_of::<&str>());
    let owned: Vec<u8> = vec![10, 20, 30, 40, 50];
    let borrowed: &[u8] = &owned; // 不搬字节，只取指针 + 长度
    println!("owned 首元素地址 = {:p}，borrowed 首元素地址 = {:p}（相同 → 未复制）", &owned[0], &borrowed[0]);

    // —— 2. 组装一个假「网络包」并零拷贝提取 payload ——
    println!();
    println!("== 零拷贝提取 payload（指针算术证明无复制）==");
    let mut packet: Vec<u8> = Vec::new();
    packet.push(0x01); // flags
    packet.extend_from_slice(&0xCAFEu16.to_be_bytes()); // type
    let body: Vec<u8> = (0..8).collect(); // 8 字节 payload
    packet.extend_from_slice(&(body.len() as u16).to_be_bytes()); // payload_len
    packet.extend_from_slice(&body); // payload

    let payload = payload_of(&packet).expect("payload 应可取出");
    println!("包总长 {} 字节；payload 视图长 {} 字节", packet.len(), payload.len());
    println!("packet  @ {:p}", &packet[0]);
    println!("payload @ {:p}", payload.as_ptr());
    let header_len = 1 + 2 + 2;
    println!("payload 首地址 - packet 首地址 = {}（= 头部 {header_len} 字节，指向同一缓冲内部）",
        payload.as_ptr() as usize - packet.as_ptr() as usize);

    // —— 3. 借用输入返回两个子切片（head_and_tail） ——
    println!();
    println!("== 一次借用、两个视图 ==");
    let (head, tail) = head_and_tail(&packet).expect("长度充足");
    println!("head = {:02X?}（包前 2 字节）", head);
    println!("tail = {:02X?}（包末 2 字节，即 body 最后两个字节）", tail);

    // —— 4. chunks 与 chunks_exact：定长分块与余数的两种处理 ——
    println!();
    println!("== chunks / chunks_exact ==");
    let blob: [u8; 10] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
    println!("chunks(3)：");
    for (i, c) in blob.chunks(3).enumerate() {
        println!("  第 {i} 块 = {c:?}"); // 最后一块只有 1 个元素
    }
    let mut it = blob.chunks_exact(3);
    let c0 = it.next().expect("≥1 块");
    let c1 = it.next().expect("≥2 块");
    println!("chunks_exact(3)：前两块 {c0:?} / {c1:?}，余数 = {:?}", it.remainder());
    // 用 chunks_exact 的理想形态：等宽记录解析中「余数=坏尾」，可直接判为数据损坏
    println!("等宽记录解析惯用法：if !it.remainder().is_empty() => 尾部长短不齐，报错丢弃");

    // —— 5. 借用切片再切片：split/窗口操作全部零拷贝 ——
    println!();
    println!("== 再切分 ==");
    let frame: Vec<u8> = vec![b'k', b'v', 0, 0x01, 0x02, 0x03];
    let (meta, body2) = frame.split_at(2);
    println!("split_at(2)：meta={meta:?} body={body2:?}（仍是同一块堆内存的两个视图）");
    // 三字节窗口滚动：windows(2) 在定长结构中常用来做 CRC/校验滑窗
    let wins: Vec<&[u8]> = frame.windows(2).collect();
    println!("windows(2) 共 {} 个窗口，前两个 = {:?}", wins.len(), &wins[..2]);
}
