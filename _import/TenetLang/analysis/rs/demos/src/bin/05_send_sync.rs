// 05 · Send/Sync 并发安全演示
// 运行：cargo run --bin 05_send_sync
// 把被注释的 Rc 跨线程代码打开，编译会报 "Rc<i32> cannot be sent between threads"。

use std::sync::{mpsc, Arc, Mutex};
use std::thread;

fn main() {
    println!("== Arc<Mutex>：跨线程安全共享 ==");
    let counter = Arc::new(Mutex::new(0));
    let mut handles = vec![];

    for _ in 0..4 {
        let c = Arc::clone(&counter); // 原子引用计数，可跨线程
        handles.push(thread::spawn(move || {
            let mut n = c.lock().unwrap(); // 锁：同一时刻只有一个线程能改
            *n += 1;
        }));
    }
    for h in handles {
        h.join().unwrap();
    }
    println!("4 个线程各加 1 后: {}", *counter.lock().unwrap());

    // let rc = Rc::new(5);
    // thread::spawn(move || { println!("{}", rc); }); // ❌ Rc 不是 Send！
    // 上面这行取消注释后编译错误：Rc<i32> cannot be sent between threads safely

    println!("\n== channel：消息传递而不是共享内存 ==");
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        for i in 1..=3 {
            tx.send(i * i).unwrap();
        }
    });
    for received in rx {
        println!("收到: {received}");
    }
}
