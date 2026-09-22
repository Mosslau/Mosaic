// 来源：languages/rs/ph11-error-handling/exercises/README.md 练习 4
// 说明：panic 与 recover 边界——catch_unwind 截获 panic 并 downcast payload；
//       Mutex 中毒（poisoned）的检测与恢复：持锁线程 panic 后 lock() 返回 Err，
//       PoisonError::into_inner() 取回 MutexGuard 读数据。
//       运行本文件时 stderr 会打印 2 行 panic 消息（panic hook 即使被捕获也会输出），
//       程序退出码 0，正常继续。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-04-panic-poison-recover.rs -o /tmp/sol04
// 运行：/tmp/sol04
// 验证状态：已验证（编译零警告；panic 消息、中毒消息均为实测文本）

use std::panic;
use std::sync::{Arc, Mutex};

fn main() {
    // ===== 1) catch_unwind：截获 panic，downcast 拿回 &str payload =====
    let result = panic::catch_unwind(|| {
        panic!("服务启动失败: 端口被占用"); // 故意 panic（已包住，不会崩）
    });
    match result {
        Ok(_) => println!("未 panic"),
        Err(payload) => {
            let msg = payload
                .downcast_ref::<&str>()
                .copied()
                .unwrap_or("<非字符串 payload>");
            println!("catch 到 panic: {msg}");
            assert_eq!(msg, "服务启动失败: 端口被占用");
        }
    }

    // ===== 2) Mutex 中毒恢复：数据完好，显式处理 PoisonError =====
    let m = Arc::new(Mutex::new(vec![1, 2, 3]));
    let m2 = Arc::clone(&m);
    let handle = std::thread::spawn(move || {
        let _guard = m2.lock().unwrap(); // guard 保持存活到 panic，Drop 时标记中毒
        panic!("持锁线程处理数据时 panic"); // 故意 panic
    });
    let _ = handle.join();

    let lock_result = m.lock(); // 先绑定再 match（match m.lock() 直接写同样合法，见主文档示例 5 要点）
    match lock_result {
        Ok(guard) => println!("锁正常: {:?}", *guard),
        Err(poisoned) => {
            // 中毒恢复策略：日志记录后 into_inner 取回数据（数据本身未被破坏）
            println!("锁中毒: {poisoned}");
            let guard = poisoned.into_inner();
            println!("into_inner 取回数据: {:?}", *guard);
            assert_eq!(*guard, vec![1, 2, 3]);
        }
    }

    // ===== 3) 断言 catch_unwind 在正常路径返回 Ok =====
    let ok = panic::catch_unwind(|| 1 + 1);
    assert_eq!(ok.unwrap(), 2);
    println!("全部断言通过");
}
