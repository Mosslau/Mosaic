// 来源：languages/rs/ph12-concurrency-async/exercises/README.md 练习 3
// 说明：RwLock 读多写一——模拟一个共享配置缓存：4 个读者线程并发读 key "a" 各 1000 次，
//       1 个写者线程写 key "b"。读锁可并发、写锁独占；读者命中数与最终缓存值确定。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-03-rwlock-shared-cache.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告；命中数 [1000, 1000, 1000, 1000] 与最终缓存为实测确定值）

use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::thread;

fn main() {
    let cache = Arc::new(RwLock::new(HashMap::<String, u32>::new()));
    cache.write().unwrap().insert("a".to_string(), 1); // 预置 key "a"

    // 4 个读者并发读 key "a" 各 1000 次（读锁可同时持有 → 互不阻塞）
    let mut readers = Vec::new();
    for _ in 0..4 {
        let c = Arc::clone(&cache);
        readers.push(thread::spawn(move || {
            let mut hits = 0u32;
            for _ in 0..1000 {
                let guard = c.read().unwrap();
                if guard.contains_key("a") {
                    hits += 1;
                }
                // guard 在此 drop：立刻释放读锁
            }
            hits
        }));
    }

    // 1 个写者：写 key "b" 5 次（写锁独占）
    let c = Arc::clone(&cache);
    let writer = thread::spawn(move || {
        for i in 0..5u32 {
            let mut guard = c.write().unwrap();
            guard.insert("b".to_string(), i);
        }
    });

    let hits: Vec<u32> = readers.into_iter().map(|h| h.join().unwrap()).collect();
    writer.join().unwrap();

    let map = cache.read().unwrap();
    println!("读者命中数 = {hits:?}（每个读者都应命中 1000 次）");
    println!("最终缓存 = {map:?}（key \"b\" 应为最后一次写入的 4）");
    assert!(hits.iter().all(|&h| h == 1000), "读锁并发下命中数必须全满");
    assert_eq!(map.get("b"), Some(&4), "写锁独占下最后一次写生效");
    println!("断言通过：读并发不丢命中，写独占不交错——RwLock 语义正确");
}
