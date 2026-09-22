// 本文件故意编译失败：期望错误码 E0507（cannot move out of index of `Vec<String>`）。
// 场景：从共享引用（&Vec）后面的内容里「拿走所有权」—— 借来的数据没有所有权可让渡。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0507]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn take_head(items: &Vec<String>) -> String {
    items[0] // E0507：items[0] 在共享引用之后，不能 move 出元素
}

fn main() {
    let v = vec![String::from("a"), String::from("b")];
    println!("{}", take_head(&v));
}
