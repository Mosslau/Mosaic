// 本文件故意编译失败：期望错误码 E0506（cannot assign to `fancy.num` because it is borrowed）。
// 场景：borrowed 仍不可变借用 fancy.num，却要对同一个字段赋值 —— 读写同一内存。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0506]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
struct FancyNum {
    num: u32,
}

fn main() {
    let mut fancy = FancyNum { num: 5 };
    let borrowed = &fancy.num; // 不可变借用 fancy.num
    fancy.num = 10; // E0506：借用未结束时不能给被借用字段赋值
    println!("{borrowed}");
}
