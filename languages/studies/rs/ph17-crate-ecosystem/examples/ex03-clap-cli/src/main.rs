// examples/ex03-clap-cli/src/main.rs —— clap 4 derive 教学（主文档 3.6 / 示例 3）
// 验证环境：rustc/cargo 1.92.0（edition 2021）；依赖 clap 4（features = ["derive"]，crates.io 拉取，可配 rsproxy）
// 编译/运行/测试：
//   cargo run -- --help
//   cargo run -- greet world
//   cargo run -- --count 3 --verbose greet rust
//   cargo run -- show --json
//   cargo test
// —— 未在本环境验证
use clap::{Args, Parser, Subcommand};

/// clap derive 三件套演示：flag / 选项 / 子命令
#[derive(Parser)]
#[command(name = "ph17-demo", version, about)]
struct Cli {
    /// 详细输出开关（flag：出现即 true）
    #[arg(short, long)]
    verbose: bool,

    /// 输出重复次数（选项，带默认值）
    #[arg(short, long, default_value_t = 1)]
    count: u32,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// 向某人问好
    Greet { name: String },
    /// 打印配置（可 JSON 输出）
    Show(ShowArgs),
}

#[derive(Args)]
struct ShowArgs {
    /// 以 JSON 格式输出
    #[arg(long)]
    json: bool,
}

fn main() {
    // parse() 遇非法输入直接报错退出（带 usage 提示）；业务代码拿到的永远是合法值
    let cli = Cli::parse();

    match cli.cmd {
        Cmd::Greet { name } => {
            for _ in 0..cli.count {
                let msg = format!("hello, {name}");
                if cli.verbose {
                    println!("[ph17-demo] {msg}");
                } else {
                    println!("{msg}");
                }
            }
        }
        Cmd::Show(args) => {
            if args.json {
                // 手工拼 JSON 仅为演示；真实工程用 serde_json（见 ex02）
                println!("{{\"verbose\":{},\"count\":{}}}", cli.verbose, cli.count);
            } else {
                println!("verbose = {}, count = {}", cli.verbose, cli.count);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_greet_with_flag() {
        // parse_from：用测试输入代替真实 argv
        let cli = Cli::parse_from(["ph17-demo", "--verbose", "greet", "world"]);
        assert!(cli.verbose);
        assert!(matches!(cli.cmd, Cmd::Greet { ref name } if name == "world"));
    }

    #[test]
    fn parse_count_default() {
        // 未给 --count 时用 default_value_t = 1
        let cli = Cli::parse_from(["ph17-demo", "show"]);
        assert_eq!(cli.count, 1);
        assert!(matches!(cli.cmd, Cmd::Show(_)));
    }
}
