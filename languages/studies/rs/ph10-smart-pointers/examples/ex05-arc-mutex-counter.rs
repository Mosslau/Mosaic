// 来源：languages/rs/ph10-smart-pointers/examples/ —— 主文档第 6 章示例 5
// 说明：Arc<Mutex<T>> 线程间共享可变状态：Arc 解决「每线程一份共享句柄」（原子引用计数），
//       Mutex 解决「同时只有一个线程改」。8 线程 × 1000 次累加 = 8000（输出数字已实测）。
//       注意：多线程下 Arc 的 drop 时机由调度决定，本示例不打印 drop 顺序——顺序不定，
//       不做断言；只断言最终计数值（确定性结果）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex05-arc-mutex-counter.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告，输出 total = 8000，断言通过）

use std::sync::{Arc, Mutex};
use std::thread;

fn main() {
    let counter = Arc::new(Mutex::new(0u64));
    let mut handles = vec![];

    for _ in 0..8 {
        let c = Arc::clone(&counter); // 每线程一份 Arc（引用计数 +1，数据仍是一份）
        handles.push(thread::spawn(move || {
            for _ in 0..1000 {
                let mut guard = c.lock().unwrap(); // 加锁拿到 MutexGuard（DerefMut 到 &mut u64）
                *guard += 1;
            } // guard 离开循环体即解锁——锁的持有范围由 guard 作用域决定
        }));
    }

    for h in handles {
        h.join().unwrap(); // 等待所有线程结束，保证计数全部完成
    }

    let final_value = *counter.lock().unwrap();
    println!("total = {final_value}"); // 8 线程 × 1000 次 = 8000
    assert_eq!(final_value, 8000);
}
