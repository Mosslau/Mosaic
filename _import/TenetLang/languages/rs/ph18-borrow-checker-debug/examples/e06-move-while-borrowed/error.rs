// 本文件故意编译失败：期望错误码 E0505（cannot move out of `items` because it is borrowed）。
// 场景：first 仍借用 items 里的元素时，把整个 items move 到新变量 —— 数据随容器被移走，
// 借用却还指向旧位置，编译器在编译期就拦下这种「悬垂引用」风险。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0505]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let items = vec![1, 2, 3];
    let first = &items[0]; // 不可变借用：first 指向 items 内部
    let owned = items; // E0505：借用未结束时不能把容器 move 走
    println!("{first} 在 {} 个元素里", owned.len());
}
