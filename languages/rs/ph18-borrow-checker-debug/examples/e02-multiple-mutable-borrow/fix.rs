// 修复版（与同目录 error.rs 对照）。思路：让第一个借用「用完即止」，再开第二个。
// 依据：NLL 下可变借用活到「最后一次使用」，只要两次 &mut 的生命区间不重叠就合法。
// 验证：rustc --edition 2021 fix.rs && ./fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    let mut score = 0i32;
    let first = &mut score; // 可变借用开始
    *first += 1;
    println!("first = {first}"); // first 最后一次使用 → 该借用在此结束
    let second = &mut score; // 前一个借用已结束，允许开新的 &mut
    *second += 2;
    println!("second = {second}");
}
