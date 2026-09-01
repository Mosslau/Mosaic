// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 1
// 说明：std::fs 一站式速览——写文件、读字符串、读字节、追加写、元数据、复制，
//       以及「文件不存在」错误的 ErrorKind 判定（io::Error 结构化错误处理承接 ph11）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-fs-read-write.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告；字节数、ErrorKind、os error 2 消息均为实测；
//           错误消息文本与 OS 相关，macOS/Linux 为 "No such file or directory"）

use std::fs::{self, OpenOptions};
use std::io::{self, Write};

fn main() -> io::Result<()> {
    let dir = "/tmp/ph13-ex01";
    fs::create_dir_all(dir)?; // 递归创建目录，已存在也不报错
    let file = format!("{dir}/hello.txt");

    // ===== 1. 写：fs::write 一键写（覆盖式） =====
    fs::write(&file, "hello rust\n第二行\n")?; // &str / &[u8] 均可
    println!("1. 写入完成: {file}");

    // ===== 2. 读：read_to_string（要求合法 UTF-8） =====
    let text = fs::read_to_string(&file)?;
    println!("2. read_to_string: {} 字符 / {} 字节", text.chars().count(), text.len());
    // 注意：len() 是字节数——"第二行" 3 个汉字占 9 字节

    // ===== 3. 读：fs::read 拿到原始字节 Vec<u8>（可处理非 UTF-8 文件） =====
    let bytes = fs::read(&file)?;
    println!("3. fs::read: {} 字节, 前 5 字节 = {:?}", bytes.len(), &bytes[..5]);

    // ===== 4. 追加写：OpenOptions 精细控制 =====
    let mut f = OpenOptions::new()
        .append(true) // 追加而非覆盖；另有 .read(true) .write(true) .create(true) .truncate(true)
        .open(&file)?;
    writeln!(f, "第三行（追加）")?; // File 实现了 io::Write
    drop(f); // 显式关闭（实际靠 Drop 自动关闭，这里为清晰起见）

    // ===== 5. 元数据：大小、类型、修改时间 =====
    let meta = fs::metadata(&file)?;
    println!("5. metadata: {} 字节, is_file={}", meta.len(), meta.is_file());

    // ===== 6. 复制与重命名 =====
    let copied = fs::copy(&file, format!("{dir}/hello.bak"))?;
    println!("6. fs::copy 复制了 {copied} 字节"); // 返回复制的字节数

    // ===== 7. 错误处理：读不存在的文件 =====
    match fs::read_to_string(format!("{dir}/no-such.txt")) {
        Ok(_) => println!("7. 不可能到这里"),
        Err(e) => {
            // ErrorKind 是跨平台的结构化判定；e.to_string() 的文本与 OS 相关
            println!("7. 错误: kind={:?}, 消息={}", e.kind(), e);
            assert_eq!(e.kind(), io::ErrorKind::NotFound);
        }
    }

    // ===== 8. 清理 =====
    fs::remove_dir_all(dir)?; // 递归删除整个目录
    println!("8. 清理完成");
    Ok(())
}
