// examples/tokio/src/bin/ex10-tokio-mpsc-backpressure.rs —— 异步背压：tokio 有界通道
// 说明：tokio::sync::mpsc::channel(容量) 与 std 的 sync_channel 同构——缓冲满时
//       send 会等待；区别是 tokio 版 send().await 挂起的是**任务**而不是线程
//       （任务让出线程，线程继续服务别的任务）。慢消费者 + 有界容量 = 生产端被
//       限速，这就是背压：快生产者不会把内存/队列无限撑爆。
// 验证环境：rustc 1.92.0 + tokio 1.53.1（macOS arm64），已通过 rsproxy 镜像拉取
// 编译：cargo build --release（见 examples/tokio/Cargo.toml 头注释）
// 运行：cargo run --release --bin ex10-tokio-mpsc-backpressure
// 验证状态：已验证（tokio 1.53.1；时间点为实测：容量 2 满后生产 3/4 各挂起约 100ms，
//           直到消费者取走一条才恢复，总耗时约 500ms）

use tokio::sync::mpsc;
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    let start = std::time::Instant::now();
    let (tx, mut rx) = mpsc::channel(2); // 容量 2：超过即触发背压

    // 生产者任务：连续发 5 条
    let producer = tokio::spawn(async move {
        for i in 0..5u32 {
            tx.send(i).await.expect("消费者已关闭"); // 缓冲满时**挂起任务**（异步背压）
            println!("生产 {i} @ {}ms", start.elapsed().as_millis());
        }
    });

    // 慢消费者：每 100ms 取一条（模拟慢下游）
    while let Some(v) = rx.recv().await {
        println!("消费 {v} @ {}ms", start.elapsed().as_millis());
        sleep(Duration::from_millis(100)).await;
    }
    producer.await.expect("生产者任务 panic");
    println!("异步背压演示完成：send().await 挂起的是任务不是线程（总耗时约 500ms）");
}
