//! ex06-rs-ownership.rs —— Rust 消费三种跨语言所有权约定
//! （CString / 调用方缓冲区 / 数组借用 / repr(C) 结构体）
//!
//! 编译（macOS）：
//!   cc -Wall -Wextra -std=c11 -dynamiclib bufio.c -o /tmp/ph14-ex/libbufio.dylib
//!   rustc --edition 2021 -D warnings ex06-rs-ownership.rs -L /tmp/ph14-ex \
//!         -l bufio -o /tmp/ph14-ex/ex06-rs
//! 运行：/tmp/ph14-ex/ex06-rs
//!
//! 验证环境：rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）
//! 要点：
//!   - 约定 1：C 分配的内存必须用 C 侧 bufio_str_free 释放——
//!     Rust 的 drop 不会管它（这不是 Box，是 C 的 malloc）
//!   - 约定 2：缓冲区由 Rust 分配（Vec），C 只写，生命周期在 Rust 侧
//!   - 约定 3：C 只读借用 Rust 数组，调用期间数组必须保持存活
//!   - 结构体：#[repr(C)] 保证与 C 布局一致，才能按值跨边界传递

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_longlong};

#[repr(C)]                       // 与 C 的 bufio_pt 布局一致
#[derive(Debug, PartialEq)]
struct BufioPt {
    x: c_int,
    y: c_int,
}

#[link(name = "bufio")]
extern "C" {
    fn bufio_str_dup(s: *const c_char) -> *mut c_char;
    fn bufio_str_free(s: *mut c_char);
    fn bufio_str_copy(dst: *mut c_char, cap: usize, s: *const c_char) -> usize;
    fn bufio_sum(arr: *const c_int, n: usize) -> c_longlong;
    fn bufio_pt_add(a: BufioPt, b: BufioPt) -> BufioPt;
}

fn main() {
    // 约定 1：C 分配 → 必须用 C 侧 bufio_str_free 释放
    let src = CString::new("malloc'd by C").expect("不含 NUL");
    let dup = unsafe { bufio_str_dup(src.as_ptr()) };
    assert!(!dup.is_null(), "bufio_str_dup 返回 NULL");
    let dup_str = unsafe { CStr::from_ptr(dup) }.to_string_lossy();
    println!("rs 约定1: dup={}", dup_str);
    unsafe { bufio_str_free(dup) };          // 释放回到 C 侧

    // 约定 2：Rust 分配缓冲区，C 只写（返回需要的长度）
    let mut buf = vec![0u8; 32];
    let need = unsafe {
        bufio_str_copy(buf.as_mut_ptr() as *mut c_char, buf.len(),
                       c"caller buffer".as_ptr())
    };
    let written = std::str::from_utf8(&buf[..need]).expect("C 写的是 UTF-8");
    assert_eq!(written, "caller buffer");
    println!("rs 约定2: buf={} need={}", written, need);

    // 约定 3：C 只读借用 Rust 数组
    let arr = [1i32, 2, 3, 4, 5];
    let sum = unsafe { bufio_sum(arr.as_ptr(), arr.len()) };
    assert_eq!(sum, 15);
    println!("rs 约定3: sum={}", sum);

    // repr(C) 结构体按值传递
    let r = unsafe {
        bufio_pt_add(BufioPt { x: 10, y: 20 }, BufioPt { x: 30, y: 40 })
    };
    assert_eq!(r, BufioPt { x: 40, y: 60 });
    println!("rs struct: (10,20)+(30,40)=({},{})", r.x, r.y);
    println!("rs-ownership: 全部断言通过");
}
