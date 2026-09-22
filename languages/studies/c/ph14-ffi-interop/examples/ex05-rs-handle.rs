//! ex05-rs-handle.rs —— Rust 调 session 句柄库：extern "C" + 空指针检查 + 错误码
//!
//! 编译（macOS）：
//!   cc -Wall -Wextra -std=c11 -dynamiclib session.c -o /tmp/ph14-ex/libsession.dylib
//!   rustc --edition 2021 -D warnings ex05-rs-handle.rs -L /tmp/ph14-ex \
//!         -l session -o /tmp/ph14-ex/ex05-rs
//! 运行：/tmp/ph14-ex/ex05-rs
//!
//! 验证环境：rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）
//! 要点：
//!   - opaque 句柄在 Rust 侧就是裸指针（*mut c_void / *const c_void），
//!     不拆解内部布局——安全边界靠"永远只在 C 函数之间传递"维持
//!   - create 失败返回 NULL：Rust 侧必须判空，不能直接解引用
//!   - 错误码与消息：err_out 出参 + session_strerror；常量在两侧
//!     各自定义，数值必须一致（0 / -1 / -2）

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_longlong};

// 与 session.h 的枚举数值一一对应（跨语言契约；完整枚举 0/-1/-2，
// 这里只列出本示例用到的）
const SESSION_OK: c_int = 0;
const SESSION_ERR_BADARG: c_int = -1;

#[link(name = "session")]
extern "C" {
    fn session_create(name: *const c_char, err_out: *mut c_int) -> *mut std::ffi::c_void;
    fn session_name(s: *const std::ffi::c_void) -> *const c_char;
    fn session_add(s: *mut std::ffi::c_void, v: i32) -> c_int;
    fn session_total(s: *const std::ffi::c_void) -> c_longlong;
    fn session_destroy(s: *mut std::ffi::c_void) -> c_int;
    fn session_strerror(err: c_int) -> *const c_char;
}

fn err_str(err: c_int) -> String {
    let p = unsafe { session_strerror(err) };
    if p.is_null() {
        String::from("<null>")
    } else {
        unsafe { CStr::from_ptr(p) }.to_string_lossy().into_owned()
    }
}

fn main() {
    let name = CString::new("rs-caller").expect("不含 NUL");
    let mut err: c_int = SESSION_OK;
    let s = unsafe { session_create(name.as_ptr(), &mut err) };
    assert!(!s.is_null(), "create 失败: {}", err_str(err));

    let n = unsafe { session_name(s) };
    assert!(!n.is_null(), "session_name 返回 NULL");
    let name_str = unsafe { CStr::from_ptr(n) }.to_string_lossy();
    println!("rs: create 成功 name={}", name_str);

    assert_eq!(unsafe { session_add(s, 40) }, SESSION_OK);
    assert_eq!(unsafe { session_add(s, 2) }, SESSION_OK);
    let total = unsafe { session_total(s) };
    assert_eq!(total, 42, "total != 42");
    println!("rs: total={}", total);

    let rc = unsafe { session_destroy(s) };        // 谁 create 谁 destroy
    assert_eq!(rc, SESSION_OK, "destroy 失败: {}", err_str(rc));

    // 错误路径：空 name → NULL + BADARG + 消息
    let bad = CString::new("").expect("空串不含 NUL");
    let mut err2: c_int = SESSION_OK;
    let p = unsafe { session_create(bad.as_ptr(), &mut err2) };
    assert!(p.is_null(), "空 name 应返回 NULL");
    assert_eq!(err2, SESSION_ERR_BADARG, "错误码应为 -1");
    println!("rs: 空 name → NULL, err={} msg={}", err2, err_str(err2));
    println!("rs-handle: 全部断言通过");
}
