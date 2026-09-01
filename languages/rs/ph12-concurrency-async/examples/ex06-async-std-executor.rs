// examples/ex06-async-std-executor.rs —— 纯 std 的 async/await：自写极简 executor
// 说明：不用任何第三方 crate，用 std 亲手实现「async fn → Future → 轮询 → 唤醒」链路：
//       1) async fn 被编译成状态机 Future；2) executor 反复 poll，Pending 就挂起；
//       3) waker 在"可以继续了"时唤醒 executor 再 poll。这就是任务调度的最小形态。
//       演示两个调度器：block_on（单任务）与 block_on_many（多任务轮询，谁 Ready 谁完成）。
// 注意：这是教学极简实现（单线程、无任务窃取、无优先级）；生产用 tokio（见 examples/tokio/）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex06-async-std-executor.rs -o /tmp/ex06
// 运行：/tmp/ex06
// 验证状态：已验证（编译零警告；tick 间隔与完成顺序为实测，单线程调度器下确定）

use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::task::{Context, Poll, Wake, Waker};
use std::thread;
use std::thread::Thread;
use std::time::{Duration, Instant};

// ===== 1. 极简 Waker：唤醒 = unpark 轮询线程 =====
struct SpinWaker(Thread);
impl Wake for SpinWaker {
    fn wake(self: Arc<Self>) {
        self.0.unpark(); // 通知 executor 线程：有任务就绪，再 poll 一轮
    }
}

// ===== 2. 极简 Timer：一个真正"会等待"的 Future =====
struct Timer {
    deadline: Instant,
    armed: bool, // 是否已注册唤醒线程（只注册一次）
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
            Poll::Ready(()) // 到点：本轮就绪
        } else {
            if !self.armed {
                self.armed = true;
                let waker = cx.waker().clone(); // 拿到"唤醒令牌"
                let deadline = self.deadline;
                // 教学简化：一个计时线程负责到点唤醒（tokio 用 I/O 事件循环，不占线程）
                thread::spawn(move || {
                    let now = Instant::now();
                    if deadline > now {
                        thread::sleep(deadline - now);
                    }
                    waker.wake();
                });
            }
            Poll::Pending // 尚未就绪：挂起，等 waker 唤醒后再 poll
        }
    }
}

// ===== 3. block_on：轮询单个 Future 直到 Ready =====
fn block_on<F: Future>(fut: F) -> F::Output {
    let mut fut = Box::pin(fut); // 固定到堆上（Pin 的堆版本，避免 unsafe）
    let waker = Waker::from(Arc::new(SpinWaker(thread::current())));
    let mut cx = Context::from_waker(&waker);
    loop {
        match fut.as_mut().poll(&mut cx) {
            Poll::Ready(v) => return v,
            Poll::Pending => thread::park(), // 挂起当前线程，等 waker 唤醒
        }
    }
}

// ===== 4. block_on_many：极简多任务调度器（轮询全部任务，谁 Ready 谁完成）=====
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
                continue; // 已完成的任务不再 poll
            }
            if let Poll::Ready(v) = task.as_mut().poll(&mut cx) {
                done[i] = true;
                outputs.push(v);
                progressed = true;
            }
        }
        if !progressed {
            thread::park(); // 本轮没有一个任务完成：挂起，等任一 Timer 唤醒
        }
    }
    outputs
}

// ===== 5. async fn：.await 挂起/恢复，编译成状态机 =====
async fn countdown(label: &str, steps: u32) -> u32 {
    let mut total = 0u32;
    for i in 0..steps {
        Timer::new(80).await; // 等待 80ms：挂起并让出调度（非阻塞等待）
        total += 1;
        println!("{label}: tick {i}（累计 {total}）");
    }
    total
}

fn main() {
    // A. 单个 async fn + block_on
    let n = block_on(countdown("A", 3));
    println!("A. countdown 完成，总 tick = {n}");

    // B. 极简调度器并发 3 个任务（步数不同 → 完成顺序确定：先短后长）
    let start = Instant::now();
    let outputs = block_on_many(vec![
        countdown("B-task-1", 2), // 2 ticks ≈ 160ms
        countdown("B-task-2", 3), // 3 ticks ≈ 240ms
        countdown("B-task-3", 4), // 4 ticks ≈ 320ms
    ]);
    println!("B. 总耗时约 {}ms，输出 = {outputs:?}", start.elapsed().as_millis());
    println!(
        "调度器原理：每个 .await 点都是状态机的一个状态；Pending 让出，Ready 推进 —— 这就是 async 的非阻塞本质"
    );
}
