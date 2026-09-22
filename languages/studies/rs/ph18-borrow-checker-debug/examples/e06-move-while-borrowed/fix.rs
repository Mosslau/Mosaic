// 修复版（与同目录 error.rs 对照）。思路：先结束借用，再 move 容器。
// 把 first 的「最后一次使用」提前到 move 之前，借用区间随即收口。
// 验证：rustc --edition 2021 fix.rs -o /tmp/e06-move-while-borrowed-fix && /tmp/e06-move-while-borrowed-fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    let items = vec![1, 2, 3];
    let first = &items[0];
    println!("first = {first}"); // first 最后一次使用 → 借用结束
    let owned = items; // 借用已收口，move 容器安全（数据随 owned 继续存活）
    println!("容器总长 {}", owned.len());
}
