// project/src/main.rs —— 命令行计算器：循环读算式求值，含单元测试
// 验证环境：rustc/cargo 1.92.0（edition 2021）
// 构建：cargo build        运行：cargo run        测试：cargo test
// 已验证：cargo test 全部通过；cargo run 交互验证 3+4=7、除零提示、非法格式提示、q 退出

use std::io;

/// 计算 `a <op> b`，除零返回 None。
fn calc(a: f64, op: &str, b: f64) -> Option<f64> {
    match op {
        "+" => Some(a + b),
        "-" => Some(a - b),
        "*" => Some(a * b),
        "/" => {
            if b != 0.0 {
                Some(a / b)
            } else {
                None // 除零
            }
        }
        _ => None, // 不支持的运算符
    }
}

/// 解析一行输入为 (操作数, 运算符, 操作数)，失败返回 None。
fn parse_line(line: &str) -> Option<(f64, &str, f64)> {
    let parts: Vec<&str> = line.split_whitespace().collect();
    if parts.len() != 3 {
        return None;
    }
    let a = parts[0].parse().ok()?;
    let b = parts[2].parse().ok()?;
    Some((a, parts[1], b))
}

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

        if line.eq_ignore_ascii_case("q") {
            break;
        }

        match parse_line(line) {
            None => println!("错误: 输入格式不正确，应为 <数> <运算符> <数>"),
            Some((a, op, b)) => match calc(a, op, b) {
                Some(result) => println!("{:.2}", result),
                None if op == "/" => println!("错误: 除数为零"),
                None => println!("不支持的操作符 '{}'", op),
            },
        }
    }
    println!("再见");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_two_numbers() {
        assert_eq!(calc(3.0, "+", 4.0), Some(7.0));
    }

    #[test]
    fn divide_produces_fraction() {
        assert_eq!(calc(10.0, "/", 4.0), Some(2.5));
    }

    #[test]
    fn divide_by_zero_returns_none() {
        assert_eq!(calc(1.0, "/", 0.0), None);
    }

    #[test]
    fn unsupported_operator_returns_none() {
        assert_eq!(calc(5.0, "^", 2.0), None);
    }

    #[test]
    fn parse_valid_expression() {
        assert_eq!(parse_line("3 + 4"), Some((3.0, "+", 4.0)));
    }

    #[test]
    fn parse_rejects_bad_format() {
        assert_eq!(parse_line("abc"), None);
        assert_eq!(parse_line("1 +"), None);
    }

    #[test]
    fn parse_rejects_non_number_operand() {
        assert_eq!(parse_line("x + 4"), None);
    }
}
