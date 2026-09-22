// 修复版（与同目录 error.rs 对照）。方案：用「值」代替「引用」。
// i32 是 Copy 类型，items[0] 索引取副本零成本，取完就不再持有对 items 的借用。
// 另一种等价修法：把 println! 挪到 push 之前让借用提前收口（见 e04）。
// 验证：rustc --edition 2021 fix.rs -o /tmp/e03-shared-then-mut-fix && /tmp/e03-shared-then-mut-fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    let mut items = vec![1, 2, 3];
    let first = items[0]; // 取出 Copy 副本，与 items 再无借用关系
    items.push(4); // 可变借用畅通
    println!("first = {first}，现在共 {} 项", items.len());
}
