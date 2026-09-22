// 来源：languages/rs/ph12-concurrency-async/exercises/README.md 练习 1
// 说明：用 mpsc channel 汇总多个线程的结果——把 1..=100 分成 4 段，每个 worker 线程
//       算一段部分和，经通道发回主线程，主线程汇总。对应 roadmap 练习「用 channel
//       汇总多个线程结果」。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-01-channel-sum.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告；总和 5050 为实测确定值；worker 行已排序输出，
//           因通道到达顺序不定——若去掉 sort 每次运行顺序可能不同）

use std::sync::mpsc;
use std::thread;

const WORKERS: u32 = 4;
const N: u32 = 100; // 求 1..=100 的和（期望 5050）

fn main() {
    let (tx, rx) = mpsc::channel();
    let mut handles = Vec::new();
    let chunk = N / WORKERS;

    for w in 0..WORKERS {
        let tx = tx.clone(); // 每个 worker 一个 Sender 克隆（多生产者）
        handles.push(thread::spawn(move || {
            let start = w * chunk + 1;
            let end = if w == WORKERS - 1 { N } else { (w + 1) * chunk };
            let partial: u32 = (start..=end).sum(); // 本段部分和
            tx.send((w, partial)).unwrap(); // 发回主线程
        }));
    }
    drop(tx); // 主线程手里的原始 Sender 也要 drop，否则通道永不关闭

    // 主线程收集：rx 迭代器在全部 Sender drop 后结束
    let mut results: Vec<(u32, u32)> = rx.iter().collect();
    for h in handles {
        h.join().unwrap();
    }
    results.sort(); // 通道到达顺序不定，按 worker 编号排序后输出确定

    let mut total = 0u32;
    for (w, partial) in &results {
        println!("worker {w} 部分和 = {partial}");
        total += partial;
    }
    println!("总和 = {total}（期望 5050）");
    assert_eq!(total, 5050, "4 段部分和应恰好拼成 1..=100 的全和");
    println!("断言通过：所有 worker 的结果都经通道正确汇总");
}
