// 来源：languages/rs/ph12-concurrency-async/exercises/README.md 练习 5
// 说明：两部分——(1) Send/Sync 边界判断：编译期断言一组类型的属性，把「为什么」
//       写在注释里；(2) 背压：有界通道 sync_channel(3) 缓冲满时 send 阻塞，用计时
//       验证「生产者被消费者拖住」。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-05-send-sync-boundary.rs -o /tmp/sol05
// 运行：/tmp/sol05
// 验证状态：已验证（编译零警告；背压计时为实测，量级确定：第 4 次生产阻塞约 100ms
//           直到消费者开始接收；Send/Sync 断言全部编译通过）

use std::sync::{mpsc, Arc, Mutex, RwLock};
use std::thread;
use std::time::{Duration, Instant};

// 编译期"证据函数"：能实例化即证明满足约束
fn assert_send<T: Send>() {}
fn assert_sync<T: Sync>() {}

fn main() {
    // ===== 1. Send/Sync 边界判断 =====
    // 判断思路：Send = 值能跨线程转移所有权；Sync = 引用能跨线程共享。
    // 引用类型 &T 是 Send 当且仅当 T: Sync；组合类型由字段递归推导。
    assert_send::<i32>(); // 基础类型：Send + Sync
    assert_sync::<i32>();
    assert_send::<String>(); // 拥有类型：Send + Sync
    assert_sync::<String>();
    assert_send::<Vec<String>>();
    assert_sync::<Vec<String>>();
    assert_send::<Arc<Mutex<u32>>>(); // 共享可变：Arc<Mutex<T>> 是 Send + Sync
    assert_sync::<Arc<Mutex<u32>>>(); //（Mutex<T> 内部保证同一时刻只有一个可变访问）
    assert_send::<Arc<RwLock<u32>>>();
    assert_sync::<Arc<RwLock<u32>>>();
    assert_send::<mpsc::Sender<u32>>(); // 通道两端 Send：可移入线程
    assert_send::<mpsc::Receiver<u32>>(); // Receiver 是 Send 但不是 Sync（单消费者）
    assert_send::<&'static str>(); // &T: Send ⇔ T: Sync
    assert_sync::<&'static str>();

    // 反例（编译失败，错误文本已实测，取消注释即可复现）：
    //   assert_send::<Rc<u32>>();          // E0277: Rc<u32> cannot be sent between threads safely
    //   assert_sync::<Rc<u32>>();          // E0277: Rc<u32> cannot be shared between threads safely
    //   assert_sync::<Cell<u32>>();        // E0277: Cell<u32> cannot be shared between threads safely
    //   assert_sync::<RefCell<u32>>();     // E0277: RefCell<u32> cannot be shared between threads safely
    //   assert_sync::<mpsc::Receiver<u32>>(); // E0277: Receiver<u32> cannot be shared between threads safely
    println!("1. 全部 Send/Sync 断言编译通过（Rc/Cell/RefCell/裸指针的反例见注释）");

    // ===== 2. 背压：有界通道缓冲满时 send 阻塞 =====
    let (tx, rx) = mpsc::sync_channel(3); // 容量 3
    let start = Instant::now();
    let producer = thread::spawn(move || {
        for i in 0..6 {
            tx.send(i).unwrap();
            println!("2. 生产 {i} @ {:>4}ms", start.elapsed().as_millis());
        }
    });
    thread::sleep(Duration::from_millis(100)); // 消费者晚 100ms 开工
    for _ in 0..6 {
        match rx.recv_timeout(Duration::from_millis(300)) {
            Ok(v) => println!("2. 消费 {v} @ {:>4}ms", start.elapsed().as_millis()),
            Err(_) => break,
        }
    }
    producer.join().unwrap();
    println!("2. 背压演示完成：缓冲(3)满后生产者被阻塞，直到消费者取走消息");
}
