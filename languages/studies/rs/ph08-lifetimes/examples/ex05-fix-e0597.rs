// 来源：languages/rs/ph08-lifetimes/08-lifetimes.md 第 6 章示例 5
// 说明：修复 E0597（borrowed value does not live long enough）的三种方向
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex05-fix-e0597.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告，输出符合预期）
// 注意：下方被注释掉的"错误版本"故意不通过编译（错误块 1 借用逃出作用域，报 E0597；
//       错误块 2 返回局部值引用，原样报 E0106、补 <'a> 后报 E0515），仅作对照，请勿取消注释后指望 rustc 通过

// 错误版本（无法编译）：借用逃出作用域 / 返回对局部值的引用
// fn main() {
//     let r;
//     {
//         let s = String::from("hello");
//         r = &s;                 // error[E0597]：s 被 drop 时 r 还在用
//     }
//     println!("{}", r);
// }
// fn render_label(id: u64) -> &str {
//     let label = format!("record-{id}");  // label 是函数内部的拥有值
//     &label                               // 原样 error[E0106]；补 <'a> 后 error[E0515]
// }

// 排查套路：找到"引用指向的值"，问一句"这个值属于谁？"

// 修复 1：数据是新建的 → 返回拥有值 String，所有权移出函数
fn render_label(id: u64) -> String {
    format!("record-{id}")
}

// 修复 2：内容恒定 → 返回 &'static str（编译进二进制只读段，永不释放）
fn health_status() -> &'static str {
    "healthy"
}

// 修复 3：数据是传入的 → 返回输入切片（单输入，省略规则第 2 条即可）
fn trimmed(s: &str) -> &str {
    s.trim()
}

fn main() {
    println!("{}", render_label(42));  // record-42
    println!("{}", health_status());   // healthy
    println!("{}", trimmed("  ok  ")); // ok
}
