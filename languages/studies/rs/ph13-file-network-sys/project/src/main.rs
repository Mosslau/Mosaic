// 来源：languages/rs/ph13-file-network-sys/project/README.md
// 说明：日志转发器（log-forwarder）——roadmap ph13 推荐项目落地。
//       三种模式：
//         server <addr>            TCP 服务端：接收转发的日志行并打印
//         tail <file> <addr>       跟踪文件尾部增长，新增行经 TCP 转发（断线自动重连 ≤3 次）
//         demo                     自包含验收：进程内同时起服务端+日志源+转发器并断言
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings src/main.rs -o /tmp/logfwd
// 运行（三端演示）：
//   /tmp/logfwd server 127.0.0.1:9000        # 终端 1
//   /tmp/logfwd tail /tmp/app.log 127.0.0.1:9000   # 终端 2
//   echo "hello" >> /tmp/app.log             # 终端 3（或任何程序追加写）
// 自验：/tmp/logfwd demo   （输出见 README「实测输出」）
// 验证状态：已验证（编译零警告；demo 模式 5 行转发与断言全部实测通过）

use std::env;
use std::fs::{self, File};
use std::io::{self, BufRead, BufReader, Read, Seek, SeekFrom, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;
use std::time::Duration;

const MAX_RECONNECT: u32 = 3; // 断线重连上限
const POLL_MS: u64 = 50; // tail 轮询间隔

// ================= server 模式：接收并打印 =================

fn run_server(addr: &str) -> io::Result<()> {
    let listener = TcpListener::bind(addr)?;
    println!("[server] 监听 {}", listener.local_addr()?);
    for conn in listener.incoming() {
        let stream = conn?;
        let peer = stream.peer_addr()?;
        thread::spawn(move || {
            let reader = BufReader::new(stream);
            for line in reader.lines() {
                match line {
                    Ok(l) => println!("[server] {peer} │ {l}"),
                    Err(e) => {
                        println!("[server] {peer} 断开（{e}）");
                        break;
                    }
                }
            }
            println!("[server] {peer} 连接结束");
        });
    }
    Ok(())
}

// ================= tail 模式：跟踪文件 + 转发 =================

/// 带重连的发送器：连接断开后最多重连 MAX_RECONNECT 次
struct Sender {
    addr: String,
    stream: Option<TcpStream>,
}

impl Sender {
    fn connect(addr: &str) -> io::Result<Sender> {
        let stream = TcpStream::connect(addr)?;
        println!("[tail] 已连接 {addr}");
        Ok(Sender { addr: addr.to_string(), stream: Some(stream) })
    }

    /// 发送一行；失败则重连重试，重连耗尽返回 Err
    fn send_line(&mut self, line: &str) -> io::Result<()> {
        let payload = format!("{line}\n");
        let mut attempt = 0;
        loop {
            let ok = match &mut self.stream {
                Some(s) => s.write_all(payload.as_bytes()).is_ok(),
                None => false,
            };
            if ok {
                return Ok(());
            }
            attempt += 1;
            if attempt > MAX_RECONNECT {
                return Err(io::Error::new(
                    io::ErrorKind::ConnectionAborted,
                    format!("重连 {MAX_RECONNECT} 次仍失败，放弃发送 {line:?}"),
                ));
            }
            println!("[tail] 发送失败，第 {attempt} 次重连…");
            thread::sleep(Duration::from_millis(100));
            self.stream = TcpStream::connect(&self.addr).ok();
        }
    }
}

/// 跟踪文件尾部增长，把新增完整行经 sender 转发。
/// `rounds_without_new`：连续多少轮无新数据后退出（0 = 永不退出，真正 tail -f）。
/// `started`：初始 offset 定位完成后发信号（demo 用它消除「日志源抢跑」竞态）。
fn tail_file(
    path: &str,
    sender: &mut Sender,
    rounds_without_new: u32,
    started: Option<std::sync::mpsc::Sender<()>>,
) -> io::Result<u64> {
    let mut offset = fs::metadata(path).map(|m| m.len()).unwrap_or(0); // 从文件当前末尾开始
    if let Some(tx) = started {
        let _ = tx.send(()); // 通知：tail 基点已确定，日志源可以开始追加
    }
    let mut partial = String::new(); // 半行缓存：只转发以 \n 结尾的完整行
    let mut sent = 0u64;
    let mut idle = 0u32;
    loop {
        let len = fs::metadata(path).map(|m| m.len()).unwrap_or(0);
        if len > offset {
            let mut f = File::open(path)?;
            f.seek(SeekFrom::Start(offset))?;
            let mut chunk = String::new();
            f.read_to_string(&mut chunk)?;
            offset += chunk.len() as u64;
            partial.push_str(&chunk);
            // 按完整行切分，最后一段（无 \n）留到下一轮
            while let Some(idx) = partial.find('\n') {
                let line: String = partial.drain(..=idx).collect();
                sender.send_line(line.trim_end())?;
                sent += 1;
            }
            idle = 0;
        } else {
            idle += 1;
            if rounds_without_new > 0 && idle >= rounds_without_new {
                break;
            }
        }
        thread::sleep(Duration::from_millis(POLL_MS));
    }
    Ok(sent)
}

// ================= demo 模式：自包含验收 =================

fn run_demo() -> io::Result<()> {
    println!("[demo] 进程内起服务端 + 转发器 + 日志源，验证端到端转发");
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let addr = listener.local_addr()?.to_string();

    const EXPECTED: [&str; 5] = ["log line 1", "log line 2", "log line 3", "log line 4", "log line 5"];

    // 服务端线程：收满 5 行即返回收集结果
    let server = thread::spawn(move || -> Vec<String> {
        let (stream, _) = listener.accept().expect("accept 失败");
        let reader = BufReader::new(stream);
        reader.lines().take(EXPECTED.len()).map(|l| l.expect("读行失败")).collect()
    });

    // 转发器线程：tail 临时文件（连续 20 轮无新数据即退出）
    let file = "/tmp/ph13-logfwd-demo.log";
    let _ = fs::remove_file(file);
    File::create(file)?; // 空文件起步
    let addr2 = addr.clone();
    let (ready_tx, ready_rx) = std::sync::mpsc::channel::<()>();
    let forwarder = thread::spawn(move || -> io::Result<u64> {
        let mut sender = Sender::connect(&addr2)?;
        tail_file(file, &mut sender, 20, Some(ready_tx))
    });

    // 日志源：等转发器定位完 tail 基点后，每隔 30ms 追加一行
    ready_rx.recv().expect("转发器线程提前退出");
    for line in EXPECTED {
        let mut f = fs::OpenOptions::new().append(true).open(file)?;
        writeln!(f, "{line}")?;
        thread::sleep(Duration::from_millis(30));
    }

    let got = server.join().expect("服务端线程 panic");
    let sent = forwarder.join().expect("转发器线程 panic")?;
    println!("[demo] 转发器发送 {sent} 行；服务端收到 {} 行", got.len());
    for (i, l) in got.iter().enumerate() {
        println!("[demo] 收到[{}] = {l:?}", i + 1);
    }
    assert_eq!(got, EXPECTED, "转发内容必须逐行一致");
    assert_eq!(sent, 5);
    fs::remove_file(file)?;
    println!("[demo] 断言通过：5 行日志全部按序转发成功");
    Ok(())
}

// ================= 入口 =================

fn usage() -> ! {
    eprintln!("用法:");
    eprintln!("  logfwd server <addr>            接收端");
    eprintln!("  logfwd tail <file> <addr>       跟踪并转发");
    eprintln!("  logfwd demo                     自包含验收");
    std::process::exit(2);
}

fn main() -> io::Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("server") if args.len() == 2 => run_server(&args[1]),
        Some("tail") if args.len() == 3 => {
            let mut sender = Sender::connect(&args[2])?;
            let sent = tail_file(&args[1], &mut sender, 0, None)?; // 0 = 永不退出（Ctrl+C 停止）
            println!("[tail] 共转发 {sent} 行");
            Ok(())
        }
        Some("demo") if args.len() == 1 => run_demo(),
        _ => usage(),
    }
}
