// project/src/main.rs —— 配置解析器命令行入口
// 来源：project/config-parser（roadmap ph04 推荐项目「配置解析器」）
// 说明：从 stdin 或命令行参数读取配置文本，解析并打印结构化 Config 或明确错误
// 验证环境：rustc 1.92.0（cargo 1.92.0），edition 2021
// 编译：cargo build
// 运行：cargo run                  （stdin 多行配置，EOF 结束）
//       cargo run -- 'port=8080'
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use std::io::Read;
use std::process::ExitCode;

use config_parser::{parse_config_lines, Config};

/// 读取 stdin 全部内容，失败返回带原因的 Err
fn read_stdin() -> Result<String, String> {
    let mut buf = String::new();
    std::io::stdin()
        .read_to_string(&mut buf)
        .map_err(|e| format!("读取标准输入失败: {e}"))?;
    Ok(buf)
}

fn print_config(cfg: &Config) {
    println!("解析结果（结构化 Config）：");
    println!("  port         = {}", cfg.port);
    println!("  timeout_secs = {}", cfg.timeout_secs);
    println!("  debug        = {}", cfg.debug);
    println!("  log_level    = {}", cfg.log_level);
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    // 无参数时从 stdin 读多行配置，有参数时把参数当多行配置（每参数一行）
    let text = if args.is_empty() {
        match read_stdin() {
            Ok(t) => t,
            Err(e) => {
                eprintln!("错误: {e}");
                return ExitCode::FAILURE;
            }
        }
    } else {
        args.join("\n")
    };

    let lines: Vec<&str> = text.lines().collect();
    match parse_config_lines(&lines) {
        Ok(cfg) => {
            print_config(&cfg);
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("配置解析失败: {e}");
            ExitCode::FAILURE
        }
    }
}
