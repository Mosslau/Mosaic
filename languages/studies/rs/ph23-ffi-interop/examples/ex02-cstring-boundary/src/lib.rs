//! ex02：CString/CStr —— 字符串跨 FFI 边界的三种形态。
//!
//! 教学要点（对应主文档 3.3）：
//! - **C→Rust（借用方向）**：`CStr` 只是「NUL 结尾字节串」的借用视图，不拥有内存；
//!   要当 `&str` 用必须先验证 UTF-8（C 字符串只管字节，不管编码）。
//! - **内嵌 NUL**：C 字符串以首个 NUL 为终点——Rust 侧能看到的只有 NUL 之前的字节，
//!   之后的字节对 Rust 不可见。Rust→C 时若字符串含内嵌 NUL，`CString::new` 会 panic
//!   （panic 跨边界即 UB，兜底方案见 ex03）。
//! - **Rust→C（分配方向）**：`CString::into_raw` 把所有权移交给 C；「谁分配谁释放」——
//!   本文件配套导出 `ex02_free_string`，C 用完必须调它，绝不能 `free()` Rust 分配的内存
//!   （malloc 指针与 Rust 分配器指针的差异见主文档 4.3）。
//!
//! unsafe 边界最小化：裸指针只出现在 `*_shim` 形态的导出函数内、一进函数就转成安全类型；
//! 每个 unsafe 块的 soundness 前提都写在紧邻的注释里（rust-patterns 纪律）。
//!
//! 验证环境：cargo/rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）；本机实测「已验证」。

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int};

/// 返回 C 字符串的字节数（不含结尾 NUL）。`null` 指针返回 -1。
///
/// # Safety
/// `ptr` 必须指向合法的 NUL 结尾字节串，或为 null。合法 = 可读、以 NUL 收尾、
/// 生命周期覆盖本次调用。
#[no_mangle]
pub unsafe extern "C" fn ex02_bytes_len(ptr: *const c_char) -> c_int {
    if ptr.is_null() {
        return -1;
    }
    // SAFETY: 调用方保证 ptr 是合法 NUL 结尾 C 字符串（本函数 Safety 文档）。
    let cstr = unsafe { CStr::from_ptr(ptr) };
    cstr.to_bytes().len() as c_int // 只数字节，不做 UTF-8 校验
}

/// 校验 UTF-8 后返回「字符数」；非法 UTF-8 或 null 返回 -1。
/// 对比 `ex02_bytes_len`：C 的 strlen 是字节数，「字符数」需要 UTF-8 解码才能数。
///
/// # Safety
/// `ptr` 必须指向合法的 NUL 结尾字节串，或为 null。
#[no_mangle]
pub unsafe extern "C" fn ex02_utf8_chars(ptr: *const c_char) -> c_int {
    if ptr.is_null() {
        return -1;
    }
    // SAFETY: 同 ex02_bytes_len。
    let bytes = unsafe { CStr::from_ptr(ptr) }.to_bytes();
    match std::str::from_utf8(bytes) {
        Ok(s) => s.chars().count() as c_int,
        Err(_) => -1, // 字节流不是合法 UTF-8：CStr 层不报错，&str 层才暴露
    }
}

/// Rust 侧分配、把所有权移交给 C 的字符串（每次调用都是新堆分配）。
/// C 用完必须调用 `ex02_free_string` 归还——这就是「谁分配谁释放」红线的一种形态：
/// 返回的不再是 `ex01` 那种永不释放的静态字符串。
#[no_mangle]
pub extern "C" fn ex02_make_greeting() -> *mut c_char {
    // 教学性覆盖：字符串是编译期常量、无内嵌 NUL，CString::new 不可能失败，
    // expect 不会 panic；真实场景应把「可含内嵌 NUL 的输入」先校验再进 CString（见 3.3 常见错误）。
    let c = CString::new("hello from rust").expect("literal has no interior NUL");
    c.into_raw() // 移交所有权：本函数之后不再接触它，释放责任归 C 侧
}

/// 释放 `ex02_make_greeting` 分配的内存——与分配函数成对导出。
///
/// # Safety
/// `ptr` 必须是 `ex02_make_greeting` 返回、且尚未释放过的指针；null 可安全传入。
#[no_mangle]
pub unsafe extern "C" fn ex02_free_string(ptr: *mut c_char) {
    if ptr.is_null() {
        return;
    }
    // SAFETY: 调用方保证 ptr 来自 into_raw（本文件 ex02_make_greeting）且未被释放；
    // 此刻 Rust 重新成为唯一 owner，drop 会按 Rust 分配器规则回收。
    unsafe { drop(CString::from_raw(ptr)) };
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::CString;

    #[test]
    fn greeting_roundtrip_free() {
        let ptr = ex02_make_greeting();
        // SAFETY: ptr 由本函数刚分配，测试内保证生命周期覆盖到 free 为止。
        let c = unsafe { CStr::from_ptr(ptr) };
        assert_eq!(c.to_str().unwrap(), "hello from rust");
        // SAFETY: 归还同一指针。
        unsafe { ex02_free_string(ptr) };
    }

    #[test]
    fn bytes_vs_chars_on_utf8() {
        let s = CString::new("你好，Rust").unwrap();
        // SAFETY: CString 保证 NUL 结尾且生命周期覆盖本测试。
        let (b, ch) = unsafe { (ex02_bytes_len(s.as_ptr()), ex02_utf8_chars(s.as_ptr())) };
        assert_eq!(b, 13); // 「你好，Rust」= 3×3 字节（你好，）+ 4 字节（Rust）
        assert_eq!(ch, 7); // 7 个字符
    }

    #[test]
    fn invalid_utf8_detected() {
        let raw = [0xFFu8, 0xFE, 0x00]; // 非法 UTF-8 字节流（0xFF 0xFE 后跟 NUL）
                                        // SAFETY: raw 以 0x00 结尾，是合法 C 字节串；生命周期覆盖本次调用。
        let ch = unsafe { ex02_utf8_chars(raw.as_ptr() as *const c_char) };
        assert_eq!(ch, -1); // CStr 层没问题，&str 层拒绝
    }
}
