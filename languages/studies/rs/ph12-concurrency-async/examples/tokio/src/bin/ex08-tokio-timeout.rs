// examples/tokio/src/bin/ex08-tokio-timeout.rs —— 超时、取消与 JoinError
// 说明：tokio::time::timeout(时限, future) 到点取消 future 并返回 Err(Elapsed)——
//       「任务取消」在 async 世界的实现方式（drop 掉还没完成的 future）。
//       任务内部 panic 时，JoinHandle.await 返回 Err(JoinError)，可用 is_panic() 判断。
// 验证环境：rustc 1.92.0 + tokio 1.53.1（macOS arm64），已通过 rsproxy 镜像拉取
// 编译：cargo build --release（见 examples/tokio/Cargo.toml 头注释）
// 运行：cargo run --release --bin ex08-tokio-timeout
// 验证状态：已验证（tokio 1.53.1；三条输出均为实测。
//           注意：任务 panic 虽被 JoinError 收容，stderr 仍会打印 1 行 panic hook
//           输出（thread 'tokio-rt-worker' panicked ...），程序退出码 0，正常继续）

use tokio::time::{sleep, timeout, Duration};

#[tokio::main]
async fn main() {
    // 1) 超时取消：任务需要 300ms，时限只有 100ms → Err(Elapsed)
    let r1 = timeout(Duration::from_millis(100), slow(300)).await;
    match r1 {
        Ok(v) => println!("1) 完成: Ok({v})"),
        Err(_) => println!("1) 超时: Err(Elapsed)——任务在 await 点被取消（drop 未完成的 future）"),
    }

    // 2) 时限充足：任务 100ms，时限 500ms → Ok(42)
    let r2 = timeout(Duration::from_millis(500), slow(100)).await;
    println!("2) 时限内完成: Ok({})", r2.expect("不应超时"));

    // 3) 任务 panic：JoinError 带回 panic 信息，不炸掉整个进程
    let handle = tokio::spawn(async {
        panic!("任务内部出错"); // 故意 panic（被 JoinHandle.await 收容）
    });
    match handle.await {
        Ok(v) => println!("3) 任务完成: {v:?}"),
        Err(e) => println!("3) 任务失败: {e}（is_panic={}）", e.is_panic()),
    }
    println!("进程正常结束——任务级失败不会带崩运行时");
}

async fn slow(ms: u64) -> u32 {
    sleep(Duration::from_millis(ms)).await; // 挂起期间可被取消（future 被 drop）
    42
}
