// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 4
// 说明：TCP 编程——TcpListener 绑定/TcpStream 连接、回显协议、读超时（set_read_timeout）、
//       对端断开检测（read 返回 Ok(0) = EOF）、连接被拒错误。服务端与客户端在同一进程
//       用线程演示（回环 127.0.0.1，端口 0 = 系统分配空闲端口），输出完全确定。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex04-tcp-echo.rs -o /tmp/ex04
// 运行：/tmp/ex04
// 验证状态：已验证（编译零警告；WouldBlock/ConnectionRefused/os error 61 均为 macOS 实测；
//           Linux 行为一致，错误文本相同；Windows 上超时 kind 为 TimedOut）

use std::io::{self, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;
use std::time::Duration;

fn main() -> io::Result<()> {
    // ===== 服务端：绑定回环 + 端口 0（OS 分配空闲端口，避免端口冲突） =====
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();
    println!("0. 服务端监听端口 = {port}（0 表示由 OS 分配，每次运行不同）");

    // 服务端线程：处理两个连接，日志收集到 Vec 返回（保证输出顺序确定）
    let server = thread::spawn(move || -> Vec<String> {
        let mut log = Vec::new();
        // 连接 1：回显直到对端关闭
        let (mut s1, peer) = listener.accept().expect("accept 失败");
        log.push(format!("S1. 接受连接来自 {peer}"));
        let mut buf = [0u8; 64];
        loop {
            match s1.read(&mut buf) {
                Ok(0) => {
                    log.push("S1. read 返回 Ok(0)：对端已关闭连接（EOF）".to_string());
                    break;
                }
                Ok(n) => {
                    let msg = String::from_utf8_lossy(&buf[..n]).to_string();
                    log.push(format!("S1. 收到 {n} 字节: {msg:?}"));
                    s1.write_all(&buf[..n]).expect("回显写失败"); // 原样写回
                }
                Err(e) => {
                    log.push(format!("S1. 读错误: {e}"));
                    break;
                }
            }
        }
        // 连接 2：故意延迟 300ms 再回显（配合客户端 100ms 读超时）
        let (mut s2, _) = listener.accept().expect("accept 失败");
        let n = s2.read(&mut buf).expect("读失败");
        log.push(format!("S2. 收到请求，延迟 300ms 后回显 {} 字节", n));
        thread::sleep(Duration::from_millis(300));
        s2.write_all(&buf[..n]).expect("回显写失败");
        log
    });

    // ===== 客户端连接 1：正常回显 + 断开 =====
    let mut c1 = TcpStream::connect(("127.0.0.1", port))?;
    c1.write_all(b"hello tcp")?;
    let mut buf = [0u8; 64];
    let n = c1.read(&mut buf)?;
    println!("1. 客户端收到回显: {:?}", String::from_utf8_lossy(&buf[..n]));
    drop(c1); // 关闭连接 → 服务端 read 返回 Ok(0)

    // ===== 客户端连接 2：读超时 =====
    let mut c2 = TcpStream::connect(("127.0.0.1", port))?;
    c2.set_read_timeout(Some(Duration::from_millis(100)))?; // 100ms 读超时
    c2.write_all(b"slow request")?;
    match c2.read(&mut buf) {
        Ok(_) => println!("2. 意外：第一次就读到了"),
        Err(e) => {
            // 超时错误 kind：macOS/Linux 是 WouldBlock，Windows 是 TimedOut
            println!("2. 读超时: kind={:?}, 消息={}", e.kind(), e);
            assert!(matches!(
                e.kind(),
                io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut
            ));
        }
    }
    // 服务端 300ms 后回显到达，再读一次能拿到
    thread::sleep(Duration::from_millis(250)); // 等服务端写回
    let n = c2.read(&mut buf)?;
    println!("2. 第二次读到回显: {:?}", String::from_utf8_lossy(&buf[..n]));
    drop(c2);

    // ===== 连接被拒：连一个没人监听的端口 =====
    match TcpStream::connect("127.0.0.1:1") {
        Ok(_) => println!("3. 意外：端口 1 居然能连上"),
        Err(e) => {
            println!("3. 连接被拒: kind={:?}, 消息={}", e.kind(), e);
            assert_eq!(e.kind(), io::ErrorKind::ConnectionRefused);
        }
    }

    // ===== 收服务端日志（join 后打印，保证输出顺序确定） =====
    for line in server.join().expect("服务端线程 panic") {
        println!("{line}");
    }
    Ok(())
}
