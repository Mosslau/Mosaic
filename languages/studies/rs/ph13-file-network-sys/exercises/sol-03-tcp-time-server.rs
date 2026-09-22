// 来源：languages/rs/ph13-file-network-sys/exercises/README.md 练习 3
// 说明：TCP 时间戳服务器——客户端连接后服务端回发当前毫秒时间戳文本并主动关闭；
//       客户端设读超时接收，读完流（read_to_string 直到 EOF）。覆盖 accept/连接/
//       超时/对端关闭检测（对应 roadmap 练习「写一个 TCP echo server」的变体）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-03-tcp-time-server.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告；时间戳 13 位数字、WouldBlock 超时、EOF 读取均为实测）

use std::io::{self, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

fn main() -> io::Result<()> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();

    // 服务端：接受 1 个连接，故意延迟 200ms 再回发时间戳，然后主动关闭
    let server = thread::spawn(move || {
        let (mut s, peer) = listener.accept().expect("accept 失败");
        println!("S. 接受 {peer}");
        thread::sleep(Duration::from_millis(200)); // 模拟慢响应
        let ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("系统时间早于 1970")
            .as_millis();
        write!(s, "{ms}").expect("写失败");
        // s 在这里 drop → 关闭连接 → 客户端读到 EOF
    });

    // 客户端：读超时 50ms，预期第一次 read 超时（服务端 200ms 后才响应）
    let mut c = TcpStream::connect(("127.0.0.1", port))?;
    c.set_read_timeout(Some(Duration::from_millis(50)))?;
    let mut buf = [0u8; 32];
    match c.read(&mut buf) {
        Ok(_) => println!("C. 意外：第一次没超时"),
        Err(e) => {
            println!("C. 首次 read 超时: kind={:?}", e.kind());
            assert!(matches!(
                e.kind(),
                io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut
            ));
        }
    }

    // 放宽超时重读：服务端 200ms 时回发，读完后服务端关闭 → read_to_string 返回全部
    c.set_read_timeout(Some(Duration::from_millis(2000)))?;
    let mut text = String::new();
    c.read_to_string(&mut text)?; // 读到 EOF（对端关闭）才返回
    let ms: u128 = text.parse().expect("应是纯数字时间戳");
    println!("C. 收到时间戳 {ms}（{len} 位）", len = text.len());
    assert_eq!(text.len(), 13); // 毫秒时间戳当前是 13 位
    assert!(ms > 0);

    server.join().expect("服务端线程 panic");
    println!("断言通过");
    Ok(())
}
