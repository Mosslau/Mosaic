// 来源：languages/rs/ph10-smart-pointers/exercises/README.md 练习 4
// 说明：用 Arc<Mutex<_>> 做线程间计数——Arc 提供跨线程共享句柄（原子引用计数），
//       Mutex 保证同一时刻只有一个线程修改；8 线程 × 1000 次 = 8000（实测），
//       期望值由常量动态计算并用 assert_eq! 兜底。
// 注意：多线程下 Arc 的 drop 时机由调度决定（顺序不定），本练习只断言确定性计数结果。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-04-arc-mutex-counter.rs -o /tmp/sol04
// 运行：/tmp/sol04
// 验证状态：已验证（编译零警告，输出 total = 8000，断言通过）

use std::sync::{Arc, Mutex};
use std::thread;

const NTHREADS: u64 = 8;
const ITERS: u64 = 1000;

fn main() {
    let counter = Arc::new(Mutex::new(0u64));
    let mut handles = vec![];

    for _ in 0..NTHREADS {
        let c = Arc::clone(&counter);
        handles.push(thread::spawn(move || {
            for _ in 0..ITERS {
                let mut guard = c.lock().unwrap(); // 加锁 -> MutexGuard（DerefMut 到 &mut u64）
                *guard += 1;
            } // guard 离开循环体自动解锁
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    let final_value = *counter.lock().unwrap();
    println!("total = {final_value}");
    assert_eq!(final_value, NTHREADS * ITERS); // 8000
}
