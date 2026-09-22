// examples/ex01-thread-spawn-join.rs —— 线程创建、等待与返回值（thread::spawn + join）
// 说明：thread::spawn 启动新线程（1:1 映射到 OS 线程），返回 JoinHandle；
//       handle.join() 阻塞等待线程结束并取回返回值。move 闭包把数据移进线程。
// 注意：多线程打印顺序不保证——每次运行 "主线程/子线程" 行的先后可能不同（已如实标注）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-thread-spawn-join.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告；输出为实测，其中部分行顺序不定）

use std::thread;
use std::time::Duration;

fn main() {
    // ===== 1. 最简 spawn + join =====
    let handle = thread::spawn(|| {
        println!("子线程: 正在工作...");
        thread::sleep(Duration::from_millis(50));
        println!("子线程: 完成");
    });
    // 主线程不等 spawn 返回，立即继续执行——上面两行与下面这行的先后不定
    println!("主线程: 已 spawn，继续做自己的事");
    handle.join().expect("子线程 panic"); // 阻塞直到子线程结束
    println!("主线程: join 返回，子线程已结束");

    // ===== 2. spawn 的返回值：闭包返回任意 Send 值，join 取回 =====
    let handle2 = thread::spawn(|| 40 + 2);
    let answer = handle2.join().expect("线程 panic");
    println!("子线程返回值: {answer}");

    // ===== 3. 命名线程 + move 闭包 =====
    let name = String::from("worker-a");
    let handle3 = thread::Builder::new()
        .name("worker-a".into()) // 给线程起名，panic 消息与调试器可见
        .spawn(move || {
            // move：把 name 的所有权移进线程（join 后用返回值把结果带出来）。
            // 不写 move 则借用检查器拒绝——借用的 name 生命周期可能比线程短
            // （典型 E0373「borrowed data escapes outside of closure」，见主文档 3.1）
            println!("线程 {name:?} 启动");
            name.len()
        })
        .expect("spawn 失败");
    let len = handle3.join().expect("线程 panic");
    println!("线程返回长度 {len}（name 的所有权已移入线程，主线程不再持有）");

    // ===== 4. 多个线程：打印顺序不定（并发执行的本质） =====
    let mut handles = Vec::new();
    for i in 0..4 {
        handles.push(thread::spawn(move || println!("线程 {i} 打印")));
    }
    for h in handles {
        h.join().expect("线程 panic");
    }
    println!("4 个线程全部 join 完成（上面 4 行的顺序每次运行都可能不同）");
}
