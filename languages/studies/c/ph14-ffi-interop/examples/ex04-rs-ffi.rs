//! ex04-rs-ffi.rs —— Rust 用 extern "C" 调用 C 动态库 libcalc
//!
//! 编译（macOS）：
//!   cc -Wall -Wextra -std=c11 -dynamiclib calc.c -o /tmp/ph14-ex/libcalc.dylib
//!   rustc --edition 2021 -D warnings ex04-rs-ffi.rs -L /tmp/ph14-ex -l calc \
//!         -o /tmp/ph14-ex/ex04-rs
//! 运行：/tmp/ph14-ex/ex04-rs
//!
//! 验证环境：rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）
//! 要点：
//!   - `#[link(name = "calc")]` 声明链接 -l calc（找 libcalc.dylib）
//!   - `extern "C"` 块声明 C 链接函数；调用必须在 unsafe 块里，
//!     内存安全由调用方保证
//!   - 错误码：C 返回 -1 表示错误，Rust 侧按值判断
//!   - C 字符串用 CString 构造（含结尾 \0），as_ptr() 只读借用给 C

#[link(name = "calc")]
extern "C" {
    fn calc_add(a: i32, b: i32) -> i32;
    fn calc_div(a: i32, b: i32, out: *mut i32) -> i32;
    fn calc_strlen(s: *const std::os::raw::c_char) -> i32;
}

fn main() {
    // unsafe：调用外部 C 函数，跨越语言边界
    let sum = unsafe { calc_add(20, 22) };
    assert_eq!(sum, 42, "calc_add(20,22) != 42");

    let mut q: i32 = 0;
    let rc = unsafe { calc_div(84, 2, &mut q) };
    assert_eq!((rc, q), (0, 42), "calc_div(84,2) 结果不符");

    let rc0 = unsafe { calc_div(1, 0, &mut q) };
    assert_eq!(rc0, -1, "calc_div(1,0) 应返回 -1 错误码");

    // CString 构造含 \0 的 C 字符串；指针借用给 C 直到调用返回
    let s = std::ffi::CString::new("hello").expect("不含 NUL，构造不应失败");
    let n = unsafe { calc_strlen(s.as_ptr()) };
    assert_eq!(n, 5, "calc_strlen(hello) != 5");

    println!("rs-ffi: calc_add(20,22)=42 calc_div(84,2)=rc0/42 \
              calc_div(1,0)=rc-1 strlen(hello)=5 —— 全部断言通过");
}
