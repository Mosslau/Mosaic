// examples/tokio/src/bin/ex07-tokio-tasks.rs —— tokio 任务与定时器
// 说明：tokio::spawn 把 async 块交给运行时调度（相当于线程版的 thread::spawn，
//       但任务在线程池上多路复用，数量可达几十万）；tokio::time::sleep 是非阻塞
//       定时器——挂起当前任务、让出线程，到点由运行时唤醒（不是占着线程 sleep）。
// 验证环境：rustc 1.92.0 + tokio 1.53.1（macOS arm64），已通过 rsproxy 镜像拉取
// 编译：cargo build --release（见 examples/tokio/Cargo.toml 头注释）
// 运行：cargo run --release --bin ex07-tokio-tasks
// 验证状态：已验证（tokio 1.53.1；输出为实测，完成顺序确定：52 → 152 → 252ms）

use tokio::time::{sleep, Duration};

#[tokio::main] // 宏：把 main 变成 async fn，并自动创建并驱动 tokio 运行时
async fn main() {
    let start = std::time::Instant::now();

    // tokio::spawn：返回 JoinHandle<T>（T 是任务返回值）
    let handles: Vec<_> = (0..3u64)
        .map(|i| {
            tokio::spawn(async move {
                sleep(Duration::from_millis(100 * i + 50)).await; // 非阻塞等待
                println!("任务 {i} 完成 @ {}ms", start.elapsed().as_millis());
                i * 10
            })
        })
        .collect();

    // JoinHandle 本身是 Future：.await 等待任务结束并取回返回值
    let mut sum = 0u64;
    for h in handles {
        sum += h.await.expect("任务 panic"); // 任务 panic 时返回 Err(JoinError)
    }
    println!("全部任务完成 @ {}ms，返回值之和 = {sum}", start.elapsed().as_millis());
}
