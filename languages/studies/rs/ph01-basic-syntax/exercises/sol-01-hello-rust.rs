// exercises/sol-01-hello-rust.rs —— Hello Rust：let 绑定 + println! 占位符 + if 表达式
// 验证环境：rustc 1.92.0
// 编译：rustc sol-01-hello-rust.rs -o sol01
// 运行：./sol01
// 已验证：本环境编译零警告，输出 Hello, Rust! 与问候语

fn main() {
    println!("Hello, Rust!");

    let name = "CodeBuddy";
    println!("你好，{}！", name);

    // if 是表达式：整个分支结构求出一个值绑定给 greeting
    let hour = 20;
    let greeting = if hour < 12 {
        "早上好"
    } else if hour < 18 {
        "下午好"
    } else {
        "晚上好"
    };
    println!("{}，{}！", greeting, name);
}
