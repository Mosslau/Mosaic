// 本文件故意编译失败：期望错误码 E0499（borrowed as mutable more than once）。
// 场景：同一数据同时存在两个「活跃」的可变借用——两个 &mut 都想在后期被使用。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0499]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let mut score = 0i32;
    let first = &mut score; // 第 1 个可变借用
    let second = &mut score; // E0499：同一数据上出现第 2 个可变借用
    *first += 1;
    *second += 2;
    println!("{first} {second}");
}
