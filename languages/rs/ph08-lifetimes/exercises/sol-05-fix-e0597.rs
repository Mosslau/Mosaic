// 来源：languages/rs/ph08-lifetimes/exercises/README.md 练习 5
// 说明：复现并修复 E0597 的三种方向——拥有值 / &'static / 输入切片
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-05-fix-e0597.rs -o /tmp/sol05
// 运行：/tmp/sol05
// 验证状态：已验证（编译零警告，输出符合预期）

// 故意不通过编译：演示返回局部值引用的错误——原样报 E0106、补 <'a> 后报 E0515，请勿取消注释指望 rustc 通过
// fn make_tag(id: u64) -> &str {
//     let tag = format!("tag-{id}"); // tag 是函数内部的拥有值
//     &tag                           // 原样 error[E0106]；补 <'a> 后 error[E0515]：tag 在函数返回时被 drop，引用悬空
// }

// 排查套路：找到"引用指向的值"，问一句"这个值属于谁？"

// 修复 1：数据属于函数内部（新建的）→ 返回拥有值 String，所有权移出函数
fn make_tag_owned(id: u64) -> String {
    format!("tag-{id}")
}

// 修复 2：数据属于程序级常量（内容恒定）→ 返回 &'static str，编译进二进制只读段
fn health_status() -> &'static str {
    "healthy"
}

// 修复 3：数据属于调用方（传入的）→ 返回输入切片；单输入，省略规则第 2 条自动补全
fn first_line(text: &str) -> &str {
    text.lines().next().unwrap_or("")
}

fn main() {
    println!("{}", make_tag_owned(42));           // tag-42
    println!("{}", health_status());              // healthy
    println!("{}", first_line("first\nsecond"));  // first
}
