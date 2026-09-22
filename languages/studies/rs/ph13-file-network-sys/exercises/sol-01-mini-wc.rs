// 来源：languages/rs/ph13-file-network-sys/exercises/README.md 练习 1
// 说明：迷你 wc——用 BufReader 逐行处理文件，统计行数/词数/字节数（不整读进内存）。
//       对应 roadmap 练习「读取大文件并逐行处理」。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-01-mini-wc.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告；3 行 / 6 词 / 64 字节为实测确定值，与 `wc` 命令口径一致：
//           字节数含换行符；词数按 split_whitespace——连续非空白算 1 词）

use std::fs::{self, File};
use std::io::{self, BufRead, BufReader};

/// 统计结果
#[derive(Debug, PartialEq)]
struct Counts {
    lines: u64,
    words: u64,
    bytes: u64,
}

/// 逐行统计（流式：内存占用与文件大小无关）
fn count(path: &str) -> io::Result<Counts> {
    let reader = BufReader::new(File::open(path)?);
    let mut c = Counts { lines: 0, words: 0, bytes: 0 };
    for line in reader.lines() {
        let line = line?; // 每行是 Result<String>，不含 '\n'
        c.lines += 1;
        c.words += line.split_whitespace().count() as u64;
        c.bytes += line.len() as u64 + 1; // +1 补回换行符（与 wc -c 口径一致）
    }
    Ok(c)
}

fn main() -> io::Result<()> {
    // 造一个已知内容的测试文件（3 行）
    let dir = "/tmp/ph13-sol01";
    fs::create_dir_all(dir)?;
    let path = format!("{dir}/sample.txt");
    fs::write(&path, "hello world\nrust io 编程\n最后一行没有词数统计问题\n")?;

    let c = count(&path)?;
    println!("行数 = {}, 词数 = {}, 字节数 = {}", c.lines, c.words, c.bytes);

    // 实测验证（按 split_whitespace，连续非空白算 1 词）：
    // "hello world"=2 词 11+1 字节；"rust io 编程"=3 词 14+1 字节；"最后一行…问题"=1 词 36+1 字节（12 个汉字）
    assert_eq!(c.lines, 3);
    assert_eq!(c.words, 6);
    assert_eq!(c.bytes, 64); // UTF-8 中文每字 3 字节，+1 是每行的 '\n'

    // 错误路径：文件不存在
    match count(&format!("{dir}/nope.txt")) {
        Ok(_) => println!("意外成功"),
        Err(e) => println!("不存在文件: kind={:?}", e.kind()),
    }

    fs::remove_dir_all(dir)?;
    println!("断言通过");
    Ok(())
}
