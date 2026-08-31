// examples/ex04-box-dyn-error-context.rs —— 错误上下文包装（Box<dyn Error>），主文档第 6 章示例 4
// 说明：错误上下文包装（Box<dyn Error>）。
//       Box<dyn Error> 是「开集」：任何实现 Error 的错误都能装进去（类型擦除），
//       map_err 把上下文信息包进 String 再 .into() 装箱；层与层之间用 ? 直接传播。
//       运行前提：普通运行（/tmp/ex04）打印三组场景、退出码 0；
//       带 --fail 运行（/tmp/ex04 --fail）故意让 main 返回 Err——运行时打印
//       `Error: "..."` 到 stderr 并以退出码 1 结束（演示 main -> Result 的退出行为）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex04-box-dyn-error-context.rs -o /tmp/ex04
// 运行：/tmp/ex04  或  /tmp/ex04 --fail
// 验证状态：已验证（编译零警告；两种运行模式的输出均为实测结果）

use std::error::Error;

// 第一层：读文件，失败时把「哪个文件」包进错误上下文
fn load(path: &str) -> Result<String, Box<dyn Error>> {
    std::fs::read_to_string(path).map_err(|e| format!("读取 {path} 失败: {e}").into())
}

// 第二层：逐行解析，失败时把「哪一行」包进上下文；load 的错误经 ? 直接向上传播
fn parse_numbers(path: &str) -> Result<Vec<u32>, Box<dyn Error>> {
    let text = load(path)?; // Box<dyn Error> 与 Box<dyn Error> 之间 ? 直接传
    text.lines()
        .enumerate()
        .map(|(i, line)| {
            line.trim()
                .parse::<u32>()
                .map_err(|e| format!("{path} 第 {} 行不是数字: {e}", i + 1).into())
        })
        .collect()
}

fn main() -> Result<(), Box<dyn Error>> {
    std::fs::write("/tmp/ph11-ex04-ok.txt", "10\n20\n30\n").unwrap();
    std::fs::write("/tmp/ph11-ex04-bad.txt", "10\nabc\n30\n").unwrap();

    for p in ["/tmp/ph11-ex04-ok.txt", "/tmp/ph11-ex04-bad.txt", "/tmp/ph11-ex04-missing.txt"] {
        match parse_numbers(p) {
            Ok(v) => println!("OK   {p} -> {v:?}"),
            Err(e) => println!("ERR  {p} -> {e:?}"),
        }
    }

    // --fail 模式：故意让 ? 在 main 里失败——运行时打印 Error: "..." 并以退出码 1 结束
    if std::env::args().any(|a| a == "--fail") {
        let _text = load("/tmp/ph11-ex04-missing.txt")?;
    }
    Ok(())
}
