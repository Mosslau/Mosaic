// examples/ex05-panic-recover-boundary.rs —— panic 与 recover 边界（catch_unwind / Mutex 中毒恢复），主文档第 6 章示例 5
// 说明：panic 与 recover 边界。
//       panic = 不可恢复的不变量破坏（unwind 逐层 drop 局部变量）；recover 手段：
//       catch_unwind（截获 panic，UnwindSafe 约束）、Mutex 中毒恢复（PoisonError +
//       into_inner 取回数据）。运行本文件时 stderr 会打印 3 行 panic 消息——
//       这是被 catch_unwind 捕获的 panic 的钩子输出（panic hook 仍会打印），
//       程序本身退出码 0，正常继续。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex05-panic-recover-boundary.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告；panic 消息、中毒消息均为实测文本）

use std::panic;

fn main() {
    // ===== recover 1：catch_unwind 截获 panic，拿回 payload =====
    let result = panic::catch_unwind(|| {
        panic!("配置缺失: app.toml"); // 故意 panic（已用 catch_unwind 包住，不会崩）
    });
    match result {
        Ok(_) => println!("未 panic"),
        Err(payload) => {
            let msg = payload
                .downcast_ref::<&str>()
                .copied()
                .unwrap_or("<非字符串 payload>");
            println!("catch 到 panic，消息 = {msg:?}"); // "配置缺失: app.toml"
        }
    }

    // ===== recover 2：unwrap 在 Err 上 panic，消息含错误值 =====
    let r2 = panic::catch_unwind(|| {
        let x: Result<u32, &str> = Err("parse failed");
        let _ = x.unwrap(); // 故意 unwrap（已用 catch_unwind 包住）
    });
    println!("unwrap Err 是否 panic: {}", r2.is_err()); // true

    // ===== recover 3：Mutex 中毒（poisoned）的恢复 =====
    // 持锁线程 panic -> guard 的 Drop 把锁标记为中毒 -> 后续 lock() 返回 Err。
    // 工程化处理：PoisonError::into_inner() 取回 MutexGuard 读数据（数据本身完好）。
    use std::sync::{Arc, Mutex};
    let m = Arc::new(Mutex::new(42u32));
    let m2 = Arc::clone(&m);
    let handle = std::thread::spawn(move || {
        let _guard = m2.lock().unwrap(); // guard 保持存活到 panic，Drop 时标记中毒
        panic!("持锁线程 panic");
    });
    let _ = handle.join();

    let lock_result = m.lock(); // 先绑定再 match，便于在 Err 分支用 into_inner() 取回 guard（match m.lock() 直接写同样合法）
    match lock_result {
        Ok(g) => println!("锁正常: {}", *g),
        Err(poisoned) => {
            println!("锁中毒: {}", poisoned); // poisoned lock: another task failed inside
            let inner = poisoned.into_inner(); // 取回 MutexGuard（数据未被破坏）
            println!("into_inner 取回数据: {}", *inner); // 42
        }
    }
}
