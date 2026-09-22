// examples/crates/src/bin/ex06-bytes-crate.rs —— bytes crate：Bytes/BytesMut 引用计数零拷贝切片
// 对应主文档 3.5。演示：Bytes 的 clone 只加引用计数（不复制）、slice/split_to 在共享缓冲上
// 切出子视图、BytesMut 从 Vec 接管缓冲（freeze 转 Bytes 零拷贝）、用 Buf trait 做帧解码时
// copy_to_bytes 直接产出引用计数子视图 —— 流式 length-prefix 解析的「免 memmove」版（对照 ex04 的 compact）。
// 验证环境：cargo 1.92.0，依赖 bytes 1.12.1（已在 Cargo.toml 锁定）。构建/运行：
//   cd examples/crates
//   CARGO_TARGET_DIR=/tmp/ph19-target cargo run --bin ex06-bytes-crate
// 验证状态：已验证（cargo 1.92.0 / bytes 1.12.1，aarch64-apple-darwin）。
use bytes::{Buf, Bytes, BytesMut};

fn main() {
    // —— 1. Bytes 是「引用计数的字节视图」：clone 免费 ——
    println!("== Bytes 廉价 clone（引用计数，非复制）==");
    let a: Bytes = Bytes::from_static(b"0123456789abcdef");
    let b = a.clone(); // 引用计数 +1，底层字节只有一份
    println!(
        "a.as_ptr() = {:p}，b.as_ptr() = {:p}（相同 → 同一份数据）",
        a.as_ptr(),
        b.as_ptr()
    );
    println!("a.len() = {}, b.len() = {}", a.len(), b.len());
    drop(a);
    println!("drop(a) 后 b 仍可用：b = {:?}", &b[..4]); // 计数减到 1，数据仍活着

    // —— 2. slice()：在共享缓冲上切子视图，不复制 ——
    println!();
    println!("== 子视图 ==");
    let mid = b.slice(2..6); // 借同一块内存的 [2..6)
    println!("b.slice(2..6) = {:?}（ptr 指向 a 的内部偏移 +2）", &mid[..]);
    println!(
        "mid.as_ptr() - b.as_ptr() = {}",
        mid.as_ptr() as usize - b.as_ptr() as usize
    );

    // —— 3. BytesMut：可增长的缓冲 → freeze 零拷贝成只读 Bytes ——
    // 网络接收侧惯用法：把数据写进 BytesMut（BufMut），凑够一帧就 freeze/切子视图。
    // 注意：Vec → Bytes 的 `Bytes::from(vec)` 若容量富余会复制一次（bytes 语义非零拷贝保证）；
    // 真正零拷贝的路径是数据本身在 bytes 缓冲里生长 —— 这里从空 BytesMut 起 build。
    println!();
    println!("== BytesMut → freeze 零拷贝 ==");
    let mut bm = BytesMut::with_capacity(32); // 网络层常直接把 read_buf 喂进来，无需 Vec
    bm.extend_from_slice(&[0xAAu8; 8]);
    bm.extend_from_slice(b"tail");
    let frozen: Bytes = bm.freeze(); // 冻结为不可变 Bytes，底层缓冲直接改姓共享，零拷贝
    let head_view = frozen.slice(..8); // 在冻结后的共享缓冲上再切视图
    println!("frozen = {:02X?}（{} 字节）", &frozen[..4], frozen.len());
    println!(
        "子视图 head_view = {:02X?}（与 frozen 共享底层分配）",
        &head_view[..]
    );

    // —— 4. Buf trait 流式解码：copy_to_bytes 产生引用计数子视图 ——
    println!();
    println!("== length-prefix 流式解码（对照 ex04 的 drain-compact 方案）==");
    // 组一段双帧数据：帧 = [len: u32 BE][payload]
    let mut raw = BytesMut::new();
    for body in [&b"hello"[..], &b"world!"[..]] {
        raw.extend_from_slice(&(body.len() as u32).to_be_bytes());
        raw.extend_from_slice(body);
    }
    let mut stream: Bytes = raw.freeze();
    let mut frames: Vec<Bytes> = Vec::new();
    while stream.len() >= 4 {
        let len = stream.get_u32() as usize; // Buf::get_u32：大端读 4 字节并 advance（内部移动头指针，非 memmove）
        if stream.len() < len {
            break; // 半帧等待
        }
        let payload = stream.copy_to_bytes(len); // 切出引用计数子视图：不再有「前缀 memmove」，缓冲零搬运
        frames.push(payload);
    }
    println!(
        "解析出 {} 帧，每帧载荷（引用计数共享同一底层分配）:",
        frames.len()
    );
    for f in &frames {
        println!("  {:?}（{}-byte slice）", &f[..], f.len());
    }
    println!("剩余半帧/尾字节 = {} 字节", stream.len());
    // 与 ex04 的 compact() 对比：ex04 用 pending.drain 把剩余字节前移（O(n) memmove）；
    // bytes 的 get_u32/advance/copy_to_bytes 只是移动「当前窗口指针」，整个解码过程零字节搬运。
}
