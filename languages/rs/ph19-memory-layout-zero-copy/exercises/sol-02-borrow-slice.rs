// exercises/sol-02-borrow-slice.rs —— 练习 2 参考实现：用切片返回借用数据
// 对应 roadmap 第 19 节练习「用切片返回借用数据」与主文档 3.4/4.2（呼应 ph18 的 E0597/E0515）。
// 格式：连续多条「记录」：每条 = [klen: u16 LE][key][vlen: u16 LE][value]。
// 任务核心：函数不拥有数据、只借用 —— 返回的 key/value 切片引用输入缓冲内部，全程零分配。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-02-borrow-slice.rs -o /tmp/ph19-sol02 && /tmp/ph19-sol02
//   rustc --edition 2021 -D warnings --test sol-02-borrow-slice.rs -o /tmp/ph19-sol02-t && /tmp/ph19-sol02-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。

/// 读出第 idx 条记录，返回 (key, value) 两个借用输入的子切片。
/// 返回类型带生命周期 'a：结果随输入缓冲存活 —— 缓冲活得够久才成立（ph08/ph18 的核心）。
fn borrow_record<'a>(buf: &'a [u8], idx: usize) -> Option<(&'a [u8], &'a [u8])> {
    let mut pos = 0usize;
    let mut seen = 0usize;
    while pos < buf.len() {
        // 一条记录的定界：先读两个长度字段
        let klen = u16::from_le_bytes(buf.get(pos..pos + 2)?.try_into().ok()?) as usize;
        let key = buf.get(pos + 2..pos + 2 + klen)?;
        let vlen_pos = pos + 2 + klen;
        let vlen = u16::from_le_bytes(buf.get(vlen_pos..vlen_pos + 2)?.try_into().ok()?) as usize;
        let value = buf.get(vlen_pos + 2..vlen_pos + 2 + vlen)?;
        if seen == idx {
            return Some((key, value));
        }
        seen += 1;
        pos = vlen_pos + 2 + vlen; // 前进到下一条
    }
    None
}

fn build_records(items: &[(&[u8], &[u8])]) -> Vec<u8> {
    let mut out = Vec::new();
    for (k, v) in items {
        out.extend_from_slice(&(k.len() as u16).to_le_bytes());
        out.extend_from_slice(k);
        out.extend_from_slice(&(v.len() as u16).to_le_bytes());
        out.extend_from_slice(v);
    }
    out
}

fn main() {
    let buf = build_records(&[
        (b"city", b"tokyo"),
        (b"temp", b"36.5"),
        (b"hum", b"60"),
    ]);
    println!("缓冲共 {} 字节", buf.len());
    for i in 0..3 {
        let (k, v) = borrow_record(&buf, i).expect("记录存在");
        // 指针算术证明借用：返回切片与输入共享底层内存（相对偏移随记录位置变化）
        let k_off = k.as_ptr() as usize - buf.as_ptr() as usize;
        println!(
            "记录 {i}: key={}(借用于偏移 {k_off}) value={}",
            String::from_utf8_lossy(k),
            String::from_utf8_lossy(v)
        );
    }

    // 两个借用切片可以同时存活（都是只读借用），互不干扰 —— 这是& 切片的基本盘
    let (k0, v0) = borrow_record(&buf, 0).expect("记录 0");
    let (k2, v2) = borrow_record(&buf, 2).expect("记录 2");
    println!("同时持有：{}={} 与 {}={}", String::from_utf8_lossy(k0), String::from_utf8_lossy(v0),
        String::from_utf8_lossy(k2), String::from_utf8_lossy(v2));

    // —— 为什么「想返回借用却在函数内造 Vec」编不过（E0515，ph18 已修过）——
    // fn bad() -> &[u8] { let v = vec![1u8]; &v }   // 编译错误：返回指向局部变量的引用
    // 解法：返回拥有值（Vec），或像 borrow_record 一样把生命周期交给输入 —— 零拷贝要靠这个判断。
    println!();
    println!("borrow_record 对不存在的索引返回 None：{:?}", borrow_record(&buf, 99));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_requested_index() {
        let buf = build_records(&[(b"a", b"1"), (b"b", b"22"), (b"c", b"333")]);
        let (k, v) = borrow_record(&buf, 1).expect("存在");
        assert_eq!(k, b"b");
        assert_eq!(v, b"22");
    }

    #[test]
    fn returns_views_into_input() {
        let buf = build_records(&[(b"key", b"value")]);
        let (k, v) = borrow_record(&buf, 0).expect("存在");
        let base = buf.as_ptr() as usize;
        assert_eq!(k.as_ptr() as usize - base, 2); // 跳过一个 u16 klen
        assert_eq!(v.as_ptr() as usize - base, 2 + 3 + 2); // klen 后接 key(3B) 与 u16 vlen
    }

    #[test]
    fn out_of_range_is_none() {
        let buf = build_records(&[(b"a", b"1")]);
        assert!(borrow_record(&buf, 1).is_none());
        assert!(borrow_record(&buf, 5).is_none());
    }

    #[test]
    fn truncated_tail_is_none_not_panic() {
        let buf = build_records(&[(b"key", b"value")]);
        assert!(borrow_record(&buf[..buf.len() - 2], 0).is_none()); // 尾截断：vlen 读不出
    }

    #[test]
    fn multiple_borrows_coexist() {
        let buf = build_records(&[(b"a", b"1"), (b"b", b"2")]);
        let (ka, _) = borrow_record(&buf, 0).expect("记录 0");
        let (kb, _) = borrow_record(&buf, 1).expect("记录 1");
        // 两个借用的数据同时可用（只读视图无排他），缓冲仍在
        assert_eq!(ka, b"a");
        assert_eq!(kb, b"b");
        assert_eq!(buf.len(), 12); // 原缓冲不受借用影响（每条记录 2+1+2+1=6B，共 12B）
    }
}
