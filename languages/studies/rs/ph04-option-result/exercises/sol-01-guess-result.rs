// exercises/sol-01-guess-result.rs —— 练习 1 参考实现：猜数字输入改造
// 来源：exercises/README.md 练习 1（ph01 猜数字的 expect 写法改造）
// 验证环境：rustc 1.92.0
// 编译：rustc sol-01-guess-result.rs -o /tmp/sol-01-guess-result
// 运行：/tmp/sol-01-guess-result            （用内置示例）
//       /tmp/sol-01-guess-result "abc" 42   （用命令行参数）
// 验证状态：已验证（rustc 1.92.0）

/// 解析玩家输入：先裁剪空白，再解析为 u32。
///
/// 不良风格（ph01 猜数字原样）：`guess.trim().parse().expect("please type a number")`
/// —— 用户随便输入一个非数字就 panic 退出。本函数把失败变成带原因的 `Err`。
fn parse_guess(input: &str) -> Result<u32, String> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return Err("输入为空，请输入一个数字".to_string());
    }
    trimmed.parse::<u32>().map_err(|e| format!("'{}' 不是合法数字: {}", trimmed, e))
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    // 无命令行参数时用内置示例，方便直接运行观察
    let inputs: Vec<String> = if args.is_empty() {
        vec!["42".to_string(), " 17 ".to_string(), "abc".to_string(), "".to_string()]
    } else {
        args
    };

    for raw in inputs {
        match parse_guess(&raw) {
            Ok(n) => println!("输入 {:?} -> 猜的数字是 {}", raw, n),
            Err(e) => eprintln!("输入 {:?} -> 错误: {}", raw, e),
        }
    }
    println!("全部输入处理完毕，程序没有 panic");
}
