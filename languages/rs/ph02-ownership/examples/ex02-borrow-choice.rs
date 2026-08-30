// examples/ex02-borrow-choice.rs —— 函数传参的三种选择：不可变借用、可变借用、传值
// 验证环境：rustc 1.92.0
// 编译：rustc ex02-borrow-choice.rs -o ex02
// 运行：./ex02
// 已验证：本环境编译零警告，运行输出 show/append/uppercase 三组结果

fn show(s: &str) {
    println!("show: {}", s);
}

fn grow(s: &mut String) {
    s.push_str(" world");
}

fn take_and_upper(s: String) -> String {
    s.to_uppercase()
}

fn main() {
    let mut msg = String::from("hello");

    show(&msg); // 不可变借用：只读，msg 保留 ownership
    grow(&mut msg); // 可变借用：原地修改，msg 保留 ownership
    show(&msg); // 再次不可变借用，合法

    let loud = take_and_upper(msg); // 传值：ownership 转移，msg 失效
    println!("{}", loud);
    // println!("{}", msg); // 编译错误：value moved
}
