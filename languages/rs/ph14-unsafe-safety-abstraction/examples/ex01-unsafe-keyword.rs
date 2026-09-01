// examples/ex01-unsafe-keyword.rs —— unsafe 关键字：unsafe 块 / unsafe fn / 五类 unsafe 操作
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-unsafe-keyword.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告；5 段输出为实测）

use std::ffi::{c_char, CString};

/// unsafe fn：函数体是隐式 unsafe 上下文，可直接写 unsafe 操作；
/// 但调用方必须位于 unsafe 上下文（否则报 E0133，见 ex04 同族演示）。
unsafe fn double(n: i32) -> i32 {
    let mut x = n;
    let p: *mut i32 = &mut x;
    *p *= 2; // 2021 edition 下 unsafe fn 体内无需再包 unsafe 块；
             // 2024 edition 默认开启 unsafe_op_in_unsafe_fn lint，必须显式 unsafe { }
    x
}

// 通过 extern "C" 声明的外部函数（FFI）：调用它是 unsafe 操作之一
extern "C" {
    fn strlen(s: *const c_char) -> usize;
}

// union 字段访问也是 unsafe 操作
#[repr(C)]
union Bits {
    i: i32,
    f: f32,
}

fn main() {
    // ① unsafe 块：把「最小范围」的代码标记为 unsafe——最小 unsafe 边界
    let mut x = 42;
    let p: *mut i32 = &mut x;
    unsafe {
        *p += 1; // 解引用裸指针：unsafe 操作 #1
    }
    println!("1. 裸指针解引用（unsafe 块内）: x = {x}");

    // ② 调用 unsafe fn：unsafe 操作 #2（必须在 unsafe 上下文内）
    let d = unsafe { double(21) };
    println!("2. 调用 unsafe fn: double(21) = {d}");

    // ③ 调用外部函数：unsafe 操作 #3（FFI 调用基础，见 ex05/ex06）
    let s = CString::new("hello").unwrap();
    let len = unsafe { strlen(s.as_ptr()) };
    println!("3. 调用 extern fn: strlen(\"hello\") = {len}");

    // ④ union 字段访问：unsafe 操作 #4（读取会按另一种类型解释位模式）
    let u = Bits { f: 3.5 };
    let raw = unsafe { u.i }; // f32 3.5 的位模式按 i32 读（依赖平台）
    println!("4. union 字段访问: f32 3.5 的位模式按 i32 读 = {raw}");

    // ⑤ unsafe impl Send/Sync：unsafe 操作 #5（把「类型可跨线程安全」的证明责任转给开发者，
    //    本阶段只提及概念，实际使用在 ph12 并发阶段见过其存在，深入属 ph14 第 5 章）
    //    这里不实现（unsafe impl 无法在 main 里局部演示），见主文档 3.1 表格。

    // unsafe fn 之间可以互相调用（unsafe 上下文内无需再加块）
    unsafe fn inner() -> i32 {
        double(5)
    }
    println!("5. unsafe fn 内调用 unsafe fn: inner() = {}", unsafe { inner() });

    // 重要认知：unsafe 块不关闭借用检查——借用错误在 unsafe 内照常报错，
    // 完整实测演示见 ex04-borrow-check-still-on.rs（故意编译失败，实测 E0594/E0502/E0506）。
}
