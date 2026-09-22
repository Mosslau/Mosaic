// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 5
// 说明：UDP 编程——UdpSocket 无连接通信、send_to/recv_from、数据报边界保留
//       （两个 send 永远是两个 recv，不会像 TCP 那样粘包）、缓冲区过小会截断丢弃、
//       connect() 设定默认对端。两个 socket 在同一进程演示，输出完全确定。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex05-udp-datagram.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告；字节数与截断行为为实测）

use std::io;
use std::net::UdpSocket;

fn main() -> io::Result<()> {
    // ===== 1. 绑定两个 socket（端口 0 = OS 分配） =====
    let server = UdpSocket::bind("127.0.0.1:0")?;
    let client = UdpSocket::bind("127.0.0.1:0")?;
    let server_addr = server.local_addr()?;
    println!("1. server={server_addr} client={}", client.local_addr()?);

    // ===== 2. send_to / recv_from：每个数据报自带对端地址 =====
    client.send_to(b"ping", server_addr)?;
    let mut buf = [0u8; 64];
    let (n, from) = server.recv_from(&mut buf)?; // 返回 (字节数, 来源地址)
    println!("2. server 收到 {n} 字节 {:?} 来自 {from}", &buf[..n]);
    server.send_to(b"pong", from)?; // 回给来源地址
    let (n, _) = client.recv_from(&mut buf)?;
    println!("2. client 收到 {n} 字节 {:?}", &buf[..n]);

    // ===== 3. 数据报边界保留：UDP 没有「粘包」 =====
    client.send_to(b"ab", server_addr)?;
    client.send_to(b"cdef", server_addr)?;
    let mut b1 = [0u8; 8];
    let mut b2 = [0u8; 8];
    let (m1, _) = server.recv_from(&mut b1)?; // 每个数据报对应一次 recv
    let (m2, _) = server.recv_from(&mut b2)?;
    println!(
        "3. 边界保留: {:?} ({m1} 字节) 然后 {:?} ({m2} 字节)，不会合并成 \"abcdef\"",
        &b1[..m1],
        &b2[..m2]
    );
    assert_eq!(&b1[..m1], b"ab");
    assert_eq!(&b2[..m2], b"cdef");

    // ===== 4. 缓冲区过小：超出部分直接丢弃（不报错、不拆分） =====
    client.send_to(b"0123456789", server_addr)?;
    let mut tiny = [0u8; 4];
    let (n, _) = server.recv_from(&mut tiny)?;
    println!("4. 缓冲 4 字节收 10 字节数据报: 得到 {:?}，后 6 字节被丢弃", &tiny[..n]);
    assert_eq!(n, 4);

    // ===== 5. connect()：给无连接的 UDP 设默认对端 =====
    client.connect(server_addr)?; // 之后可用 send/recv（不带地址），且只收该对端的包
    client.send(b"via connect")?;
    let (n, _) = server.recv_from(&mut buf)?;
    println!("5. connect 后 send: server 收到 {:?}", &buf[..n]);

    Ok(())
}
