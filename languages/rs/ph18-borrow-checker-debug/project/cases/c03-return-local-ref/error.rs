// 本文件故意编译失败：期望错误码 E0515（cannot return value referencing local variable `combined`）。
// 本文件头部另有机器可读标记行：// expect-error: E0515（verify.sh 据此断言）。
// 场景：函数想「先拼出结果再返回引用」—— 拼出的 String 是函数内的局部拥有数据，
//       返回引用会指向随函数返回而销毁的局部，编译器拒绝。
//       （这是 E0597「borrowed value does not live long enough」的直接返回形态，
//         编译器把这类「返回局部引用」单列为 E0515。）
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0515]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
// expect-error: E0515
fn best_of<'a>(a: &'a str, b: &'a str) -> &'a str {
    let combined = format!("{a}|{b}"); // 函数内拥有的局部 String
    combined.as_str() // E0515：不能返回对局部变量的引用
}

fn main() {
    println!("{}", best_of("x", "y"));
}
