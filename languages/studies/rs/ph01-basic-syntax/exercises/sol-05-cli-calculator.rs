// exercises/sol-05-cli-calculator.rs —— 命令行计算器：循环读算式，错误提示不崩溃
// 验证环境：rustc 1.92.0
// 编译：rustc sol-05-cli-calculator.rs -o sol05
// 运行：./sol05   （输入形如 3 + 4，q 退出）
// 已验证：本环境编译零警告；3 + 4 → 7.00；1 / 0 提示除零；5 ^ 2 提示不支持；q 退出

use std::io;

fn main() {
    println!("命令行计算器（算式形如 3 + 4，输入 q 退出）");
    let stdin = io::stdin();

    loop {
        println!("> ");
        let mut line = String::new();
        if stdin.read_line(&mut line).is_err() {
            println!("读取输入失败");
            continue;
        }
        let line = line.trim();

        if line == "q" || line == "Q" {
            break;
        }

        // 按空白切分为 [操作数, 运算符, 操作数]
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() != 3 {
            println!("错误: 输入格式不正确，应为 <数> <运算符> <数>");
            continue;
        }

        let a: f64 = match parts[0].parse() {
            Ok(n) => n,
            Err(_) => {
                println!("错误: '{}' 不是有效数字", parts[0]);
                continue;
            }
        };
        let b: f64 = match parts[2].parse() {
            Ok(n) => n,
            Err(_) => {
                println!("错误: '{}' 不是有效数字", parts[2]);
                continue;
            }
        };

        match parts[1] {
            "+" => println!("{:.2}", a + b),
            "-" => println!("{:.2}", a - b),
            "*" => println!("{:.2}", a * b),
            "/" => {
                if b != 0.0 {
                    println!("{:.2}", a / b);
                } else {
                    println!("错误: 除数为零");
                }
            }
            op => println!("不支持的操作符 '{}'", op),
        }
    }
    println!("再见");
}
