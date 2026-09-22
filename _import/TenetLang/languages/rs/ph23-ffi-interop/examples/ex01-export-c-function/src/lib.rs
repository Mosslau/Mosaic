//! ex01：把 Rust 函数导出成 C 可调用库（staticlib + cdylib 两种形态，见 Cargo.toml）。
//!
//! 教学要点：
//! - `extern "C"` 声明调用约定（ABI），`#[no_mangle]` 关闭符号名改编，二者缺一不可；
//! - 导出函数只使用 ABI 稳定类型（C 整数、C 字符串指针）——不把 String/Vec/Result
//!   直接放上边界；
//! - 本示例刻意不处理 panic 与内存所有权（全部参数是 Copy 标量），跨边界 panic 防护
//!   见 ex03，所有权转移见 ex07。
//!
//! 验证环境：cargo/rustc 1.92.0 + Apple clang 21.0.0（macOS arm64），本机实测标注「已验证」。

use std::ffi::CStr;
use std::os::raw::{c_char, c_int};

/// 加法：最简导出形态。调用约定与符号名都由属性声明，C 侧只需手写 extern 声明即可调用。
#[no_mangle]
pub extern "C" fn ex01_add(a: c_int, b: c_int) -> c_int {
    a + b
}

/// 乘法。
#[no_mangle]
pub extern "C" fn ex01_mul(a: c_int, b: c_int) -> c_int {
    a * b
}

/// 返回一个永不释放的静态 C 字符串指针：`c"..."` 字面量（Rust 1.77+）构造的是
/// 编译期存放、NUL 结尾的 `&CStr`，生命周期 `'static`，C 侧只读不释放即可——这是
/// 「Rust 侧分配、永不要求 C 侧释放」的最简单合法案例（完整规则见主文档 3.6/3.3）。
static IMPL_TAG: &CStr = c"ex01-rust-cdylib";

#[no_mangle]
pub extern "C" fn ex01_impl_name() -> *const c_char {
    IMPL_TAG.as_ptr()
}
