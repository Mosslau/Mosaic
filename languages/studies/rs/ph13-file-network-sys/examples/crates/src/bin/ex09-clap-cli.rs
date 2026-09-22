// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 9
// 说明：clap derive 版命令行解析——struct 即 CLI 定义、自动生成 --help、类型转换与
//       默认值、解析错误的友好提示。与 ex06 手写版对照：clap 替你做了解析/校验/帮助。
//       为保证输出确定，用 try_parse_from 喂固定参数向量演示（真实程序用 Cli::parse()）。
// 验证环境：rustc 1.92.0（macOS arm64）；clap 4.6.6（rsproxy 拉取）
// 构建：cd examples/crates && CARGO_TARGET_DIR=/tmp/ph13-target cargo run --release --bin ex09-clap-cli
// 验证状态：已验证（clap 4.6.6；解析结果、help 文本首行、错误提示为实测）

use clap::Parser;

/// 日志转发器命令行（doc 注释自动变成 --help 里的说明文字）
#[derive(Parser, Debug)]
#[command(name = "logfwd", version = "0.1.0", about = "日志转发器：tail 文件并经 TCP 转发")]
struct Cli {
    /// 要监听的日志文件
    input: String, // 位置参数（必填）

    /// 详细输出
    #[arg(short, long)] // -v / --verbose
    verbose: bool,

    /// 转发目标地址
    #[arg(short, long, default_value = "127.0.0.1:9000")] // 缺省值
    server: String,

    /// 重连次数上限
    #[arg(short = 'n', long, default_value_t = 3)] // 非字符串默认值用 default_value_t
    retries: u32,
}

fn main() {
    // ===== 1. 正常解析（try_parse_from 便于演示与测试；真实程序用 Cli::parse()） =====
    let cli = Cli::try_parse_from(["logfwd", "-v", "-n", "5", "app.log"]).expect("解析应成功");
    println!("1. 解析结果: {cli:?}");
    assert_eq!(cli.server, "127.0.0.1:9000"); // 默认值生效

    // ===== 2. --help：clap 自动生成（打印首行验证） =====
    let err = Cli::try_parse_from(["logfwd", "--help"]).unwrap_err();
    let help = err.to_string();
    println!("2. --help 首行: {}", help.lines().next().unwrap());

    // ===== 3. 缺必填参数：clap 给出友好错误并提示 --help =====
    let err = Cli::try_parse_from(["logfwd"]).unwrap_err();
    println!("3. 缺参数错误首行: {}", err.to_string().lines().next().unwrap());

    // ===== 4. 类型错误：-n abc 不是数字 =====
    let err = Cli::try_parse_from(["logfwd", "-n", "abc", "x.log"]).unwrap_err();
    println!("4. 类型错误首行: {}", err.to_string().lines().next().unwrap());

    // 真实程序的入口就一行：let cli = Cli::parse(); // 解析失败自动打印错误并 exit(2)
}
