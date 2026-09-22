// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 6
// 说明：纯 std 手写命令行参数解析——std::env::args、长短选项、带值选项、位置参数、
//       解析错误与用法提示。这是 clap 的「裸机版」：理解 clap 替你做了什么。
//       为聚焦参数解析本身，解析目标用固定向量演示（env::args 也可直接代入，见末尾）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex06-args-manual.rs -o /tmp/ex06
// 运行：/tmp/ex06（也可 /tmp/ex06 -v -n 3 file.txt 实测真实参数路径）
// 验证状态：已验证（编译零警告；解析结果与错误消息为实测）

use std::env;

/// 解析结果：Verbose 开关、重复次数、输入文件（位置参数）
#[derive(Debug, PartialEq)]
struct Config {
    verbose: bool,
    count: u32,
    input: String,
}

fn usage(prog: &str) -> String {
    format!("用法: {prog} [-v|--verbose] [-n|--count <次数>] <输入文件>")
}

/// 手写解析器：遍历 args（跳过 args[0] 程序名）
fn parse_args<I: Iterator<Item = String>>(mut args: I) -> Result<Config, String> {
    let prog = args.next().unwrap_or_else(|| "prog".to_string()); // args[0]
    let mut verbose = false;
    let mut count = 1u32;
    let mut input: Option<String> = None;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "-v" | "--verbose" => verbose = true,
            "-n" | "--count" => {
                // 带值选项：消费下一个参数
                let val = args
                    .next()
                    .ok_or_else(|| format!("-n/--count 缺少值\n{}", usage(&prog)))?;
                count = val
                    .parse()
                    .map_err(|_| format!("无效的次数 {val:?}（应为正整数）\n{}", usage(&prog)))?;
            }
            _ if arg.starts_with('-') => {
                return Err(format!("未知选项 {arg:?}\n{}", usage(&prog)));
            }
            _ => {
                if input.is_some() {
                    return Err(format!("多余的位置参数 {arg:?}\n{}", usage(&prog)));
                }
                input = Some(arg);
            }
        }
    }

    let input = input.ok_or_else(|| format!("缺少输入文件\n{}", usage(&prog)))?;
    Ok(Config { verbose, count, input })
}

fn main() {
    // ===== 1. 真实参数（随调用方式而变，只打印个数） =====
    let real: Vec<String> = env::args().collect();
    println!("1. 真实参数个数 = {}（含程序名 args[0]）", real.len());

    // ===== 2. 用固定向量演示解析（输出确定，便于教学与断言） =====
    let demo = vec!["demo", "-v", "--count", "3", "input.txt"]
        .into_iter()
        .map(String::from);
    match parse_args(demo) {
        Ok(cfg) => println!("2. 解析成功: {cfg:?}"),
        Err(e) => println!("2. 解析失败: {e}"),
    }

    // ===== 3. 错误路径：未知选项 / 缺值 / 缺位置参数 =====
    for (label, argv) in [
        ("未知选项", vec!["demo", "--verbse", "x.txt"]),
        ("缺值", vec!["demo", "-n"]),
        ("缺输入文件", vec!["demo", "-v"]),
    ] {
        match parse_args(argv.into_iter().map(String::from)) {
            Ok(cfg) => println!("3. {label}: 意外成功 {cfg:?}"),
            Err(e) => println!("3. {label} → {}", e.lines().next().unwrap()),
        }
    }

    // ===== 4. 想接真实参数？把 demo 换成 env::args() 即可 =====
    // if let Ok(cfg) = parse_args(env::args()) { /* 用 cfg */ }
}
