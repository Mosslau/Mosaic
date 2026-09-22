// examples/ex03-arc-mutex-counter.rs —— 共享可变状态：Arc<Mutex<T>> 计数器
// 说明：Arc = 原子引用计数（多线程共享所有权），Mutex = 互斥锁（同一时刻一个线程
//       能拿到可变访问）。数据竞争在编译期被排除：裸 &mut 无法跨线程，必须经 Mutex。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex03-arc-mutex-counter.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告；最终计数 800000 为实测，确定性结果）

use std::sync::{Arc, Mutex};
use std::thread;

fn main() {
    const THREADS: u32 = 8;        // 8 个线程
    const INCREMENTS: u32 = 100_000; // 每个线程自增 10 万次

    let counter = Arc::new(Mutex::new(0u32)); // 共享：Arc 让每个线程持有同一份计数
    let mut handles = Vec::new();

    for _ in 0..THREADS {
        let counter = Arc::clone(&counter); // 引用计数 +1，代价是原子操作
        handles.push(thread::spawn(move || {
            for _ in 0..INCREMENTS {
                let mut guard = counter.lock().expect("锁中毒"); // 抢锁，拿 MutexGuard
                *guard += 1;
                // guard 在本行结束处 drop：立即解锁，下一轮再抢（细粒度临界区）
            }
        }));
    }

    for h in handles {
        h.join().unwrap(); // 等全部线程结束再读数
    }

    let final_count = *counter.lock().unwrap();
    let expected = THREADS * INCREMENTS;
    println!("最终计数 = {final_count}（期望 {expected} = {THREADS} × {INCREMENTS}）");
    assert_eq!(final_count, expected, "计数必须精确：锁保证每次自增原子");
    println!("断言通过：无数据竞争，计数精确（若去掉锁会因竞争而小于 {expected}，见主文档 4.2）");
}
