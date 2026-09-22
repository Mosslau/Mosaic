// 本文件故意编译失败：期望错误码 E0503（value used after it was mutably borrowed）。
// 场景：显式手写的 &mut 是「普通可变借用、立即激活」，不享受两阶段借用 ——
//       同一表达式的参数求值从左到右进行：第 1 个参数已借走 x，第 2 个参数还想读 x。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0503]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn set(a: &mut i32, b: i32) {
    *a = b;
}

fn main() {
    let mut x = 1;
    set(&mut x, x); // E0503：参数 1 已可变借用 x；参数 2 求值时 x 还在借用中
    println!("{x}");
}
