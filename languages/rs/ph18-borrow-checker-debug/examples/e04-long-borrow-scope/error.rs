// 本文件故意编译失败：期望错误码 E0502。示范「长借用」的典型形态：
// 两个不可变借用横跨一次 push，而它们最后一次使用发生在 push 之后。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0502]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let mut items = vec![1, 2, 3];
    let a = &items[0]; // 借用区间从这里开始……
    let b = &items[1];
    items.push(4); // E0502：push 需要 &mut，而 a/b 在 push 之后仍要使用
    println!("{a} + {b}");
}
