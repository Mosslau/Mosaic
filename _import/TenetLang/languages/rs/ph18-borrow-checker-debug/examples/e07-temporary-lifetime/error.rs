// 本文件故意编译失败：期望错误码 E0716（temporary value dropped while borrowed）。
// 场景：把对「临时值」的引用塞进集合 —— &String::from(...) 引用的临时值在语句结束就被销毁。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0716]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let mut tags: Vec<&str> = Vec::new();
    tags.push(&String::from("hot")); // E0716：临时 String 在本语句结束即 drop，引用悬空
    println!("{tags:?}");
}
