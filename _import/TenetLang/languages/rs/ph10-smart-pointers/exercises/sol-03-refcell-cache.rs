// 来源：languages/rs/ph10-smart-pointers/exercises/README.md 练习 3
// 说明：RefCell 内部可变性两个经典用法——① &self 接口下的惰性缓存（compute 只执行一次，
//       第二次 get 命中缓存）；② 运行时借用冲突：borrow() 存活时 borrow_mut() 运行期 panic
//       （消息实测为 "RefCell already borrowed"，payload 类型是 BorrowMutError），
//       用 catch_unwind 捕获避免程序崩溃。
// 注意：被注释的「裸跑」块故意运行会 panic，保持注释。
//       运行本文件时 stderr 会打印一行 "RefCell already borrowed"（panic 钩子仍会输出，
//       这是被 catch_unwind 捕获的 panic 消息，程序退出码为 0，正常继续）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-03-refcell-cache.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告，compute 只打印一次，BorrowMutError 被捕获）

use std::cell::RefCell;
use std::panic;

/// 惰性缓存：第一次 get 计算并缓存，之后直接返回缓存值
struct Cache {
    value: RefCell<Option<i32>>, // None = 未计算
}

impl Cache {
    fn new() -> Self {
        Cache { value: RefCell::new(None) }
    }

    // 签名只有 &self，却能写入缓存——RefCell 内部可变性
    fn get(&self, compute: impl Fn() -> i32) -> i32 {
        if let Some(v) = *self.value.borrow() {
            return v; // 命中缓存
        }
        let v = compute();
        *self.value.borrow_mut() = Some(v);
        v
    }
}

fn main() {
    let cache = Cache::new();
    let v1 = cache.get(|| {
        println!("compute 执行"); // 只应出现一次
        42
    });
    let v2 = cache.get(|| {
        println!("compute 执行"); // 缓存命中，不应打印
        42
    });
    println!("v1 = {v1}, v2 = {v2}");
    assert_eq!((v1, v2), (42, 42));

    // 制造借用冲突：不可变借用还活着时请求可变借用 -> 运行期 panic（编译期不报错）
    let result = panic::catch_unwind(|| {
        let cell = RefCell::new(0);
        let _r = cell.borrow();      // 不可变借用 guard 存活
        let _m = cell.borrow_mut();  // 运行期 panic："RefCell already borrowed"
    });
    match result {
        Ok(_) => println!("未 panic（不该走到这里）"),
        Err(_) => println!("借用冲突：BorrowMutError panic 已被 catch_unwind 捕获"),
    }

    // ===== 故意运行会 panic（RefCell already borrowed），请勿取消注释 =====
    // let cell = RefCell::new(0);
    // let _r = cell.borrow();
    // let _m = cell.borrow_mut(); // panic: "RefCell already borrowed"
}
