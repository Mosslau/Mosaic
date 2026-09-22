// 本文件故意编译失败：期望错误码 E0508（cannot move out of type `[String; 2]`, a non-copy array）。
// 场景：数组长度编译期固定、元素内联存放 —— 想单独移走一个元素会留下「空洞」，数组不允许。
//       （对比：Vec 有独立堆缓冲，remove 可以把后续元素前移填补空洞，因此允许。）
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0508]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let arr: [String; 2] = [String::from("a"), String::from("b")];
    let s = arr[0]; // E0508：不能从非 Copy 数组中移出单个元素
    println!("{s}");
}
