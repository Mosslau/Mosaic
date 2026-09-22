// 修复版（与同目录 error.rs 对照）。
// 思路：没有长期持有引用的必要 —— 读值直接用（借用即时收口），之后再赋值。
// 验证：rustc --edition 2021 fix.rs -o /tmp/sol-01-case2-e0506-fix && /tmp/sol-01-case2-e0506-fix（已验证：rustc 1.92.0 / macOS arm64）。
struct FancyNum {
    num: u32,
}

fn main() {
    let mut fancy = FancyNum { num: 5 };
    println!("改前 num = {}", fancy.num); // 借用只存在于本语句内
    fancy.num = 10; // 读已完成，赋值畅通
    println!("改后 num = {}", fancy.num);
}
