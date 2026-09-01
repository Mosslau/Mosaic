// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 2
// 说明：缓冲 I/O——BufReader 逐行读大文件（不整读进内存）、BufWriter 批量写、
//       flush 的时机（BufWriter 缓存不落盘的风险）。同时实现一个迷你 wc。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex02-bufio-lines.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告；行数/词数/字节数为实测确定值；耗时随机器而异）

use std::fs::{self, File};
use std::io::{self, BufRead, BufReader, BufWriter, Write};
use std::time::Instant;

fn main() -> io::Result<()> {
    let dir = "/tmp/ph13-ex02";
    fs::create_dir_all(dir)?;
    let big = format!("{dir}/big.txt");

    // ===== 1. BufWriter 批量写：1 万行 =====
    let t = Instant::now();
    let file = File::create(&big)?;
    let mut w = BufWriter::new(file); // 默认 8 KiB 缓冲
    for i in 1..=10_000 {
        writeln!(w, "line {i} the quick brown fox")?; // 每行 26 + i 的位数 字节（含 \n）
    }
    w.flush()?; // 关键！缓冲里的最后一批数据要 flush 才真正落盘
    //（BufWriter 的 Drop 也会尝试 flush，但会忽略错误——显式 flush 才能拿到错误）
    println!("1. BufWriter 写 10000 行耗时 {:?}", t.elapsed());

    // ===== 2. BufReader 逐行读 + 迷你 wc（行数/词数/字节数） =====
    let t = Instant::now();
    let file = File::open(&big)?;
    let reader = BufReader::new(file); // 默认 8 KiB 缓冲，read_line 不再每次 syscall
    let (mut lines, mut words, mut bytes) = (0u64, 0u64, 0u64);
    for line in reader.lines() {
        // lines() 返回迭代器，每行是 io::Result<String>（不含换行符）
        let line = line?;
        lines += 1;
        words += line.split_whitespace().count() as u64;
        bytes += line.len() as u64 + 1; // +1 补回被剥掉的 '\n'
    }
    println!("2. wc: {lines} 行 / {words} 词 / {bytes} 字节, 耗时 {:?}", t.elapsed());
    assert_eq!(lines, 10_000);
    assert_eq!(words, 60_000); // 每行 6 个词
    assert_eq!(bytes, 298_894); // 10000×26 + 行号位数总和 38894（实测值）

    // ===== 3. 对比：无缓冲逐字节 read() 的代价 =====
    // read_line 每次只 syscall 一次读 8 KiB；若自己循环 file.read(&mut [0u8;1])
    // 每次只读 1 字节，24 万字节 = 24 万次 syscall，慢几个数量级（这里不实测，避免拖慢示例）

    // ===== 4. read_line 复用缓冲（避免每行分配 String） =====
    let file = File::open(&big)?;
    let mut reader = BufReader::new(file);
    let mut buf = String::new();
    let mut first = String::new();
    while reader.read_line(&mut buf)? > 0 {
        // read_line 返回读取的字节数，0 表示 EOF；buf 末尾含 '\n'
        if first.is_empty() {
            first = buf.trim_end().to_string();
        }
        buf.clear(); // 复用同一个 String，零分配循环
    }
    println!("4. 首行 = {first:?}");
    assert_eq!(first, "line 1 the quick brown fox");

    fs::remove_dir_all(dir)?;
    println!("5. 清理完成");
    Ok(())
}
