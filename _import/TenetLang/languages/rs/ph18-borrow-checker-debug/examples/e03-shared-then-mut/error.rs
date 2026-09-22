// 本文件故意编译失败：期望错误码 E0502（cannot borrow as mutable because also borrowed as immutable）。
// 场景：先不可变借用 items 的元素，借用在 println 之后还要用，中间却要 push（&mut）。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0502]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let mut items = vec![1, 2, 3];
    let first = &items[0]; // 不可变借用：first 引用 items 中的元素
    items.push(4); // E0502：items 仍有活跃的不可变借用，不能同时可变借用
    println!("first = {first}");
}
