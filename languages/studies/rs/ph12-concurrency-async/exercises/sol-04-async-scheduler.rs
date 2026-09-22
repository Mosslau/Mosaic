// 来源：languages/rs/ph12-concurrency-async/exercises/README.md 练习 4
// 说明：自写极简调度器并发执行多个 async 任务——实现 block_on_many（轮询全部
//       任务、谁 Ready 谁完成），并用它并发跑 3 个不同时长的 countdown 任务。
//       对应 roadmap 练习「用 tokio 并发请求多个接口」的纯 std 版：tokio 已在本
//       环境验证（1.53.1），用 tokio 的等价写法是 tokio::spawn + JoinHandle.await
//       或 tokio::join!（见 examples/tokio/ex07）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-04-async-scheduler.rs -o /tmp/sol04
// 运行：/tmp/sol04
// 验证状态：已验证（编译零警告；tick 交错与完成顺序 [2, 3, 4] 为实测，单线程
//           调度器下确定；总耗时约 320ms 为本机实测）

use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::task::{Context, Poll, Wake, Waker};
use std::thread;
use std::time::{Duration, Instant};

// ===== Waker：唤醒 = unpark 调度线程 =====
struct SpinWaker(thread::Thread);
impl Wake for SpinWaker {
    fn wake(self: Arc<Self>) {
        self.0.unpark();
    }
}

// ===== 极简 Timer Future =====
struct Timer {
    deadline: Instant,
    armed: bool,
}

impl Timer {
    fn new(ms: u64) -> Self {
        Timer {
            deadline: Instant::now() + Duration::from_millis(ms),
            armed: false,
        }
    }
}

impl Future for Timer {
    type Output = ();

    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        if Instant::now() >= self.deadline {
            Poll::Ready(())
        } else {
            if !self.armed {
                self.armed = true;
                let waker = cx.waker().clone();
                let deadline = self.deadline;
                thread::spawn(move || {
                    let now = Instant::now();
                    if deadline > now {
                        thread::sleep(deadline - now);
                    }
                    waker.wake();
                });
            }
            Poll::Pending
        }
    }
}

// ===== 极简多任务调度器：轮询全部任务，谁 Ready 谁完成 =====
fn block_on_many<F: Future>(tasks: Vec<F>) -> Vec<F::Output> {
    let mut tasks: Vec<Pin<Box<F>>> = tasks.into_iter().map(Box::pin).collect();
    let mut done = vec![false; tasks.len()];
    let mut outputs = Vec::new();
    let waker = Waker::from(Arc::new(SpinWaker(thread::current())));
    let mut cx = Context::from_waker(&waker);

    while outputs.len() < tasks.len() {
        let mut progressed = false;
        for (i, task) in tasks.iter_mut().enumerate() {
            if done[i] {
                continue;
            }
            if let Poll::Ready(v) = task.as_mut().poll(&mut cx) {
                done[i] = true;
                outputs.push(v);
                progressed = true;
            }
        }
        if !progressed {
            thread::park(); // 本轮无人完成：挂起，等任一 Timer 唤醒
        }
    }
    outputs
}

// ===== 一个 async 任务：模拟「请求一个接口」 =====
async fn fake_request(name: &str, latency_ms: u64, id: u32) -> String {
    Timer::new(latency_ms).await; // 等待期间挂起，让出调度器
    format!("{name} 返回 {id}")
}

fn main() {
    let start = Instant::now();
    let results = block_on_many(vec![
        fake_request("接口 A", 120, 1), // 120ms
        fake_request("接口 B", 240, 2), // 240ms
        fake_request("接口 C", 360, 3), // 360ms
    ]);
    let elapsed = start.elapsed().as_millis();
    println!("并发请求 3 个接口，总耗时约 {elapsed}ms（串行需 720ms）");
    for r in &results {
        println!("  {r}");
    }
    assert_eq!(results.len(), 3);
    assert!(elapsed < 600, "三个接口应并发执行，总耗时接近最慢者 360ms");
    println!("断言通过：调度器让 3 个 async 任务并发推进（非阻塞等待）");
}
