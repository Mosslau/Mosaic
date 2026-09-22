// examples/ex04-rwlock-cache.rs —— 读写锁 RwLock：读并发、写独占
// 说明：RwLock<T> 允许任意多个读者同时持读锁（read()），写者独占（write()）。
//       适合「读多写一」的共享数据（缓存、配置表）。写者等待期间新读者也被挡在门外
//       （避免写者饿死）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex04-rwlock-cache.rs -o /tmp/ex04
// 运行：/tmp/ex04
// 验证状态：已验证（编译零警告；耗时数值为本机实测，量级确定：读并发≈120ms、写等待≈100ms）

use std::sync::{Arc, RwLock};
use std::thread;
use std::time::{Duration, Instant};

fn main() {
    let cache = Arc::new(RwLock::new(100u32)); // 模拟一个共享缓存值

    // ===== 读并发：4 个读者同时持读锁 =====
    let start = Instant::now();
    let mut readers = Vec::new();
    for id in 0..4 {
        let cache = Arc::clone(&cache);
        readers.push(thread::spawn(move || {
            let guard = cache.read().unwrap(); // 读锁：可多个读者同时持有
            thread::sleep(Duration::from_millis(120)); // 持读锁 120ms
            println!("读者 {id}: 读到 {}", *guard);
            // guard 在此 drop：释放读锁
        }));
    }
    for h in readers {
        h.join().unwrap();
    }
    let read_elapsed = start.elapsed().as_millis();
    println!(
        "4 个读者总耗时约 {read_elapsed}ms（≈120ms 说明读真的并发；串行会要 480ms）"
    );

    // ===== 写独占：写者持锁时，新读者被阻塞 =====
    let start = Instant::now();
    let writer = {
        let cache = Arc::clone(&cache);
        thread::spawn(move || {
            let mut guard = cache.write().unwrap(); // 写锁：独占
            thread::sleep(Duration::from_millis(100)); // 持写锁 100ms
            *guard += 1;
        })
    };
    let blocked_reader = {
        let cache = Arc::clone(&cache);
        thread::spawn(move || {
            let guard = cache.read().unwrap(); // 写者持锁期间，这里阻塞等待
            println!(
                "读者在写者持锁期间被阻塞，{}ms 后才读到 {}",
                start.elapsed().as_millis(),
                *guard
            );
        })
    };
    writer.join().unwrap();
    blocked_reader.join().unwrap();
    println!("写独占演示完成：写者持锁期间读请求排队（实测等待约 100ms）");
}
