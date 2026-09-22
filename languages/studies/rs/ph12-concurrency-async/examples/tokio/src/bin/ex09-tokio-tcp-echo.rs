// examples/tokio/src/bin/ex09-tokio-tcp-echo.rs —— tokio 异步网络 I/O（本机回环）
// 说明：TcpListener/TcpStream 的异步版——连接、读、写都是 Future，.await 挂起而不
//       占线程，单个线程可同时服务成千上万个连接（这就是 async 网络服务的价值）。
//       （TCP/UDP 网络编程的系统化内容属于 ph13 文件、网络与系统编程阶段，
//         这里只演示「异步 I/O 长什么样」。）
// 验证环境：rustc 1.92.0 + tokio 1.53.1（macOS arm64），已通过 rsproxy 镜像拉取
// 编译：cargo build --release（见 examples/tokio/Cargo.toml 头注释）
// 运行：cargo run --release --bin ex09-tokio-tcp-echo
// 验证状态：已验证（tokio 1.53.1；回显内容与两条日志为实测，服务端端口号每次不同）

use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1) 异步 echo 服务端：绑定本机随机端口
    let listener = TcpListener::bind("127.0.0.1:0").await?; // :0 = 让系统分配端口
    let addr = listener.local_addr()?;
    let server = tokio::spawn(async move {
        let (mut sock, peer) = listener.accept().await.expect("accept 失败");
        println!("服务端: 接受连接 {peer}");
        let mut buf = [0u8; 128];
        let n = sock.read(&mut buf).await.expect("读失败");
        sock.write_all(&buf[..n]).await.expect("写失败");
        sock.shutdown().await.expect("shutdown 失败"); // 关闭写侧 → 客户端读到 EOF
    });

    // 2) 异步客户端：连接、发送、收完整回显
    let mut client = TcpStream::connect(addr).await?;
    client.write_all(b"hello tokio").await?;
    let mut reply = Vec::new();
    client.read_to_end(&mut reply).await?;
    println!("客户端: 收到回显 {:?}", String::from_utf8_lossy(&reply));

    server.await?;
    Ok(())
}
