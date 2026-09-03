// 修复版（与同目录 error.rs 对照）。
// 思路：跨「借用边界」取拥有值时只能复制（clone）；想避免复制就得换拥有所有权的参数形态。
// 两种修法都给出：① 在函数内 clone；② 改成拿走整个 Vec 的所有权，让调用方自行决定。
// 验证：rustc --edition 2021 fix.rs && ./fix（已验证：rustc 1.92.0 / macOS arm64）。
fn take_head_clone(items: &[String]) -> String {
    items[0].clone() // 借用只读，值靠自己复制一份
}

fn take_head_owned(mut items: Vec<String>) -> String {
    items.remove(0) // 拥有 Vec 后可以 move 出元素（remove 会把后面的元素前移）
}

fn main() {
    let v = vec![String::from("a"), String::from("b")];
    println!("clone 版：{}", take_head_clone(&v)); // 只借用，v 还能用
    println!("owned 版：{}", take_head_owned(v)); // 整个 Vec 被消费
}
