//! Tenet 命令行入口。
//!
//! ```text
//! tenet run <file>      # 解释执行 Tenet 源码
//! tenet codegen <file>  # 编译为 Go 源码（打印到 stdout）
//! tenet repl            # 交互式 REPL
//! ```

use std::env;
use std::process::ExitCode;

use tenet::{codegen_source, run_source};

fn usage() -> ! {
    eprintln!(
        "用法:\n  tenet run <file>     解释执行\n  tenet codegen <file> 生成 Go 源码\n  tenet repl           交互式 REPL"
    );
    std::process::exit(2);
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    let Some(cmd) = args.first() else {
        usage();
    };

    match cmd.as_str() {
        "repl" => {
            if args.len() != 1 {
                usage();
            }
            match tenet::repl::run() {
                Ok(()) => ExitCode::SUCCESS,
                Err(e) => {
                    eprintln!("{e}");
                    ExitCode::FAILURE
                }
            }
        }
        "run" => {
            if args.len() != 2 {
                usage();
            }
            let src = match std::fs::read_to_string(&args[1]) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("无法读取文件 {}: {e}", args[1]);
                    return ExitCode::FAILURE;
                }
            };
            match run_source(&src) {
                Ok(()) => ExitCode::SUCCESS,
                Err(e) => {
                    eprintln!("{e}");
                    ExitCode::FAILURE
                }
            }
        }
        "codegen" => {
            if args.len() != 2 {
                usage();
            }
            let src = match std::fs::read_to_string(&args[1]) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("无法读取文件 {}: {e}", args[1]);
                    return ExitCode::FAILURE;
                }
            };
            match codegen_source(&src) {
                Ok(go) => {
                    print!("{go}");
                    ExitCode::SUCCESS
                }
                Err(e) => {
                    eprintln!("{e}");
                    ExitCode::FAILURE
                }
            }
        }
        _ => usage(),
    }
}
