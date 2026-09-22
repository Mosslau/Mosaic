// 来源：languages/rs/ph11-error-handling/exercises/README.md 练习 3
// 说明：为 I/O 错误添加上下文——用 Box<dyn Error>（类型擦除的开集错误）做错误上下文
//       包装：map_err 把「哪个文件 / 哪一行」逐层包进上下文，层间 ? 直接传播，
//       source() 逐层遍历打印错误链。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-03-io-error-context.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告；输出已实测）

use std::error::Error;

// 第一层：读文件，失败时把「哪个文件」包进上下文
fn load(path: &str) -> Result<String, Box<dyn Error>> {
    std::fs::read_to_string(path).map_err(|e| format!("读取报告文件 {path} 失败: {e}").into())
}

// 第二层：逐行解析数字，失败时把「哪一行」包进上下文
//         （load 的错误经 ? 原样上传——Box<dyn Error> 之间无需转换）
fn parse_report(path: &str) -> Result<Vec<u32>, Box<dyn Error>> {
    let text = load(path)?;
    text.lines()
        .enumerate()
        .map(|(i, line)| {
            line.trim()
                .parse::<u32>()
                .map_err(|e| format!("解析 {path} 第 {} 行不是数字: {e}", i + 1).into())
        })
        .collect()
}

// 错误链打印：沿 source() 逐层走到根因（纯 std 的标准做法）
fn print_chain(err: &(dyn Error + 'static)) {
    let mut cur = Some(err);
    while let Some(e) = cur {
        println!("  {e}");
        cur = e.source();
    }
}

fn main() {
    std::fs::write("/tmp/ph11-sol03-data.csv", "10\n20\nabc\n40\n").unwrap();

    // 场景 A：内容不合法——上下文带「哪个文件 + 哪一行」
    let err = parse_report("/tmp/ph11-sol03-data.csv").unwrap_err();
    println!("场景 A（内容错误）: {err}");
    println!("错误链:");
    print_chain(err.as_ref());

    // 场景 B：文件不存在——上下文带「哪个文件」
    let err2 = parse_report("/tmp/ph11-sol03-missing.csv").unwrap_err();
    println!("\n场景 B（文件不存在）: {err2}");
    println!("错误链:");
    print_chain(err2.as_ref());

    // 场景 C：坏行回退——该文件含坏行，unwrap_or_else 兜底返回空 vec
    let v = parse_report("/tmp/ph11-sol03-data.csv").unwrap_or_else(|_| vec![]);
    println!("\n场景 C: {v:?}");

    // 断言兜底
    assert!(parse_report("/tmp/ph11-sol03-missing.csv").is_err());
    println!("全部断言通过");
}
