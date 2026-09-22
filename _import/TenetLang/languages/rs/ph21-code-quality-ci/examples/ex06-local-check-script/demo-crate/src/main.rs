//! demo-crate —— ex06 本地质量门禁的被测样例（干净基线）。
//!
//! 功能：把命令行传入的一串数字求和并打印。代码刻意保持「小而有质量」，
//! 用于让 `../scripts/check.sh`（ex06 根）有真实内容可查。
//!
//! 验证命令（demo-crate 目录内）：
//!   cd demo-crate
//!   CARGO_TARGET_DIR=/tmp/ph21-target cargo test
//!   cd .. && ./scripts/check.sh          # workspace 根的统一本地门禁

use std::env;

/// 把字符串参数解析成 i64；解析失败返回带参数名的错误信息。
fn parse_arg(arg: &str) -> Result<i64, String> {
    arg.parse::<i64>()
        .map_err(|_| format!("参数 `{arg}` 不是合法整数"))
}

/// 求和：空输入返回 0。
fn sum(nums: &[i64]) -> i64 {
    nums.iter().sum()
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    // 逐个校验并收集：错误信息可读、且生产路径无裸 expect（rust-patterns）
    let mut nums = Vec::with_capacity(args.len());
    for arg in &args {
        match parse_arg(arg) {
            Ok(n) => nums.push(n),
            Err(e) => {
                eprintln!("错误：{e}");
                std::process::exit(2);
            }
        }
    }
    println!("sum={}", sum(&nums));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sum_adds_positives() {
        assert_eq!(sum(&[1, 2, 3]), 6);
    }

    #[test]
    fn sum_empty_is_zero() {
        assert_eq!(sum(&[]), 0);
    }

    #[test]
    fn parse_arg_rejects_non_numeric() {
        assert!(parse_arg("abc").is_err());
        assert!(parse_arg("-42").is_ok());
    }
}
