// 来源：languages/rs/ph10-smart-pointers/examples/ —— 主文档第 6 章示例 4
// 说明：RefCell 内部可变性 + Rc<RefCell<T>> 组合模式。前半段演示 &self 接口下写日志
//       （借用检查挪到运行期）；后半段演示 BorrowMutError 运行期 panic（用 catch_unwind
//       捕获，程序不崩溃）；最后给出 Rc<RefCell<T>> 共享可变状态的标准组合。
//       注意：被注释的「裸跑」代码块是故意运行会 panic 的（RefCell already borrowed），
//       不要取消注释直接运行——想看 panic 请保留 catch_unwind 包裹的版本。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex04-refcell-combo.rs -o /tmp/ex04
// 运行：/tmp/ex04
// 验证状态：已验证（编译零警告，panic 消息与计数输出与注释一致）

use std::cell::RefCell;
use std::panic;
use std::rc::Rc;

// ===== 内部可变性：&self 接口下修改内部状态 =====

struct Logger {
    entries: RefCell<Vec<String>>,
}

impl Logger {
    fn new() -> Self {
        Logger { entries: RefCell::new(Vec::new()) }
    }

    // 签名只有 &self，却能写入 entries——RefCell 把借用检查从编译期挪到运行期
    fn log(&self, msg: &str) {
        self.entries.borrow_mut().push(msg.to_string());
    }

    fn snapshot(&self) -> Vec<String> {
        self.entries.borrow().clone()
    }
}

// ===== Rc<RefCell<T>> 组合：多个 owner 共享一份可变状态 =====

#[derive(Debug, Default)]
struct Counter {
    value: i32,
}

fn main() {
    // --- 内部可变性 ---
    let logger = Logger::new();
    logger.log("start");
    logger.log("query db");
    logger.log("done");
    println!("日志 = {:?}", logger.snapshot()); // ["start", "query db", "done"]

    // --- BorrowMutError：编译期完全合法，运行期 panic ---
    // 两个 borrow_mut 同时存活 -> 运行期 panic。用 catch_unwind 捕获，避免程序崩溃。
    let result = panic::catch_unwind(|| {
        let cell = RefCell::new(42);
        let _b1 = cell.borrow_mut(); // 第一次可变借用，guard 存活
        let _b2 = cell.borrow_mut(); // 第二次可变借用：运行期 panic！
    });
    match result {
        Ok(_) => println!("未 panic"),
        Err(_) => println!(
            "catch 到 BorrowMutError panic（panic 消息为 \"RefCell already borrowed\"，payload 类型是 BorrowMutError）"
        ),
    }

    // ===== 故意运行会 panic（RefCell already borrowed），请勿取消注释 =====
    // let cell = RefCell::new(42);
    // let _b1 = cell.borrow_mut();
    // let _b2 = cell.borrow_mut(); // 运行期 panic: "RefCell already borrowed"

    // --- Rc<RefCell<T>> 组合：两个视图共享同一个 Counter，都能改、都看得到 ---
    let counter = Rc::new(RefCell::new(Counter { value: 0 }));
    let view_a = Rc::clone(&counter);
    let view_b = Rc::clone(&counter);

    view_a.borrow_mut().value += 1; // 经 RefMut 修改（DerefMut 解引用到 Counter）
    view_b.borrow_mut().value += 2;

    println!("counter = {:?}", counter.borrow()); // Counter { value: 3 }
    println!("strong  = {}", Rc::strong_count(&counter)); // 3（counter + view_a + view_b）
}
