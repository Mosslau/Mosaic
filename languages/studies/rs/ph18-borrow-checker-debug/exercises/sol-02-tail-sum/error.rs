// 本文件故意编译失败：期望错误码 E0502。练习 2 的起点：
// 先在函数里读出「末尾 n 个元素」，push 之后还想读这段尾部 —— push 可能触发扩容搬迁，
// 编译器无法保证尾部切片依旧指向原数据，所以直接拒绝。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0502]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
/// 把「末尾 n 个元素的和」追加到 items 末尾，然后打印这段尾部内容（错误版）。
fn append_tail_sum(items: &mut Vec<u32>, n: usize) {
    let len = items.len();
    let tail: &[u32] = &items[len - n..]; // 不可变借用 items（切片）
    let sum: u32 = tail.iter().sum();
    items.push(sum); // E0502：tail 在 push 之后仍要使用
    println!("尾部 {tail:?} 之和 {sum}");
}

fn main() {
    let mut data = vec![1, 2, 3, 4];
    append_tail_sum(&mut data, 2);
    println!("{data:?}");
}
