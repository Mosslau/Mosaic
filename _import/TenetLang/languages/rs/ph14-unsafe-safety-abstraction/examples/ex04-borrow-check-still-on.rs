// examples/ex04-borrow-check-still-on.rs —— 「unsafe 不关闭借用检查」演示（故意编译失败）
// 运行前提（必读）：本文件故意包含借用检查错误（E0594/E0502/E0506）与 unsafe 调用规则错误
//   （E0133），用于演示「unsafe 块 / unsafe fn 内借用检查依然生效」。它不会编译通过——
//   请勿期待编译成功。
// 编译（预期失败）：rustc --edition 2021 -D warnings ex04-borrow-check-still-on.rs -o /tmp/ex04
// 验证状态：已验证（rustc 1.92.0，macOS arm64）——四个错误码 E0594 / E0502 / E0506 / E0133 均为实测，
//   错误文本见各函数上方注释；想单独观察某个错误，把 main 里其它调用注释掉再编译

fn demo_e0594() {
    // E0594：即使位于 unsafe 块内，也不能通过共享引用修改数据
    let x = 42;
    let p: *const i32 = &x; // 裸指针创建是安全操作
    let r: &i32 = &x; // 共享引用
    unsafe {
        let _ = *p; // 真实 unsafe 操作：解引用裸指针（让 unsafe 块"名副其实"）
        *r += 1; // 实测错误：error[E0594]: cannot assign to `*r`, which is behind a `&` reference
    }
    println!("x = {x}");
}

fn demo_e0502() {
    // E0502：unsafe 块内的可变借用与块外「仍然存活」的不可变借用冲突——借用检查跨 unsafe 边界生效
    let mut x = 42;
    let r1 = &x; // 不可变借用，最后一次使用在函数末尾（NLL：借用存活到此处）
    unsafe {
        let _ = *(&x as *const i32); // 真实 unsafe 操作
        let r2 = &mut x; // 实测错误：error[E0502]: cannot borrow `x` as mutable because it is also borrowed as immutable
        *r2 += 1;
    }
    println!("x = {x}");
    let _ = *r1; // r1 的最后一次使用——让借用真正存活到 unsafe 块之后
}

fn demo_e0506(p: *mut i32) {
    // E0506：unsafe fn 内创建的 &mut 被共享借用后不能再可变使用
    unsafe {
        let r = &mut *p; // 通过裸指针创建 &mut——合法 unsafe 操作
        let r2 = &*r; // 共享借用
        *r += 1; // 实测错误：error[E0506]: cannot assign to `*r` because it is borrowed
        let _ = *r2;
    }
}

fn demo_e0133() {
    // E0133：安全代码直接调用 unsafe fn——调用方必须位于 unsafe 块/unsafe fn 内。
    // 注意这不是借用检查错误，而是「调用 unsafe fn 缺少 unsafe 上下文」的调用规则错误。
    unsafe fn danger() -> i32 {
        42
    }
    let v = danger(); // 实测错误：error[E0133]: call to unsafe function `danger` is unsafe and requires unsafe function or block
    println!("v = {v}");
}

fn main() {
    // 四个 demo 都会报错（一次编译全部报告）；逐一观察请注释掉其它调用
    demo_e0594();
    demo_e0502();
    demo_e0506(&mut 42);
    demo_e0133();
}
