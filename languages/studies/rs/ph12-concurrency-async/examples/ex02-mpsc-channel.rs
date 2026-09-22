// examples/ex02-mpsc-channel.rs —— 通道：多生产者 → 单消费者（std::sync::mpsc）
// 说明：mpsc = Multi-Producer Single-Consumer。Sender 可 clone（多生产者），
//       Receiver 只能有一个（单消费者）。drop 掉全部 Sender 后通道关闭，
//       rx.iter() / rx.recv() 返回 Err(Disconnected)。有界版 sync_channel 演示背压。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex02-mpsc-channel.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告；输出为实测；场景 B 的收包顺序不定，已排序后打印）

use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

fn main() {
    // ===== A. 基础收发 + iter() + drop(tx) 关闭通道 =====
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        for i in 1..=3 {
            tx.send(i).unwrap(); // 发送不阻塞（无界通道）
        }
        // 闭包结束：tx 被 drop —— 通道关闭，rx.iter() 才能结束
    });
    let got: Vec<i32> = rx.iter().collect();
    println!("A. 收齐 {got:?}（iter 因所有 Sender drop 而结束）");

    // ===== B. 多生产者：clone Sender，每个线程一个 =====
    let (tx, rx) = mpsc::channel();
    let mut handles = Vec::new();
    for id in 0..3 {
        let tx = tx.clone(); // Sender<T> 是 Clone + Send，可移入线程
        handles.push(thread::spawn(move || {
            for j in 0..2 {
                tx.send((id, j)).unwrap();
            }
        }));
    }
    drop(tx); // 主线程手里的原始 tx 也要 drop，否则通道永不关闭
    for h in handles {
        h.join().unwrap(); // 先等所有生产者结束，确保消息齐全
    }
    let mut msgs: Vec<(i32, i32)> = rx.iter().collect();
    msgs.sort(); // 通道到达顺序不定，排序后输出确定
    println!("B. 多生产者共收到 {} 条: {msgs:?}", msgs.len());

    // ===== C. 背压：sync_channel(2) 有界通道，缓冲满时 send 阻塞 =====
    let (tx, rx) = mpsc::sync_channel(2); // 容量 2 的有界通道
    let start = Instant::now();
    let producer = thread::spawn(move || {
        for i in 0..4 {
            tx.send(i).unwrap(); // 第 3 个 send（i=2）在缓冲满时阻塞
            println!("C. 生产 {i} 完成 @ {:>4}ms", start.elapsed().as_millis());
        }
    });
    thread::sleep(Duration::from_millis(100)); // 消费者晚 100ms 才开始收
    for _ in 0..4 {
        match rx.recv() {
            Ok(v) => println!("C. 消费 {v} @ {:>4}ms", start.elapsed().as_millis()),
            Err(_) => break,
        }
    }
    producer.join().unwrap();
    println!("C. 背压演示完成：缓冲满时 send 阻塞，直到消费者取走消息");
}
