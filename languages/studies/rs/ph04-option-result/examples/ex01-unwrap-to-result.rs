// examples/ex01-unwrap-to-result.rs —— 把随意 unwrap 改为 Result 返回
// 来源：04-option-result.md 第 6 章示例 1
// 验证环境：rustc 1.92.0
// 编译：rustc ex01-unwrap-to-result.rs -o /tmp/ex01-unwrap-to-result
// 运行：/tmp/ex01-unwrap-to-result
// 验证状态：已验证（rustc 1.92.0）

/// 解析并校验端口号。
///
/// 不良风格：`s.parse::<u16>().unwrap()` —— 解析失败直接 panic，程序崩溃；
/// 良好风格：`map_err` + `?` 把错误连同原因传播给调用方，由调用方决定如何处理。
fn parse_and_validate(s: &str) -> Result<u16, String> {
    let port: u16 = s.parse().map_err(|e| format!("parse: {}", e))?;
    if port == 0 {
        return Err("port 0 is reserved".to_string());
    }
    Ok(port)
}

fn main() {
    // "8080" 合法；"0" 触发业务校验失败；"abc" 触发数字解析失败——三者都不 panic
    for input in ["8080", "0", "abc"] {
        match parse_and_validate(input) {
            Ok(port) => println!("'{}' -> port {}", input, port),
            Err(e) => eprintln!("'{}' -> error: {}", input, e),
        }
    }
    println!("全部输入处理完毕，程序没有 panic");
}
