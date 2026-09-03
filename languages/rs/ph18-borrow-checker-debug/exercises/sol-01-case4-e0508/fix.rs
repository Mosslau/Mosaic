// 修复版（与同目录 error.rs 对照）。
// 思路 A：整体消费数组 —— into_iter 逐个产出「拥有」的元素（edition 2021 起数组按值迭代）。
// 思路 B：改用 Vec 后可以用 remove(0) 移出元素；或只读借用元素避免 move。
// 验证：rustc --edition 2021 fix.rs && ./fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    // A：整体消费 —— 逐个 take 拥有值
    let arr: [String; 2] = [String::from("a"), String::from("b")];
    let mut iter = arr.into_iter(); // 数组整体被消费，元素逐个移交所有权
    let first = iter.next().unwrap_or_default();
    let second = iter.next().unwrap_or_default();
    println!("A: {first} / {second}");

    // B：Vec 版本 —— remove 移出并返回元素
    let mut list = vec![String::from("x"), String::from("y")];
    let head = list.remove(0);
    println!("B: 移出 {head}，还剩 {list:?}");
}
