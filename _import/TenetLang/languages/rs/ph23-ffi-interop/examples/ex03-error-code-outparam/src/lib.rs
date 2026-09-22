//! ex03：错误处理跨 FFI 边界 —— 错误码 + out 参数 + panic 护栏。
//!
//! 教学要点（对应主文档 3.5）：
//! - **`Result` 不跨边界**：`Result<T, E>` / `?` / panic 都是 Rust 侧概念，C 看不懂。
//!   边界上翻译成「错误码返回值 + out 参数写结果」。
//! - **out 参数语义**：只有成功才写 `*out`；调用方应先读返回值判断成功与否，再读 out——
//!   顺序反了会读到未初始化的垃圾。
//! - **panic 必须被 catch_unwind 兜住**：panic 的 unwind 穿过 `extern "C"` 边界是未定义行为
//!   （主文档 4.2）。所以每个边界函数第一层就 `catch_unwind` 包住内部安全实现，
//!   把「内部逻辑不该发生的 panic」翻译成错误码而不是放它穿越。
//!
//! unsafe 边界最小化：裸指针只出现在 `extern "C"` shim 里，内部实现 `*_inner` 全程 safe。
//!
//! 验证环境：cargo/rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）；本机实测「已验证」。

use std::ffi::CStr;
use std::os::raw::{c_char, c_int};

/// 边界上唯一的成功码；其余为负数错误码。错误码语义必须写进头文件/文档（见 ex05）。
pub const FFI_OK: c_int = 0;
pub const FFI_ERR_NULL: c_int = -1; // 输入指针为 null
pub const FFI_ERR_PARSE: c_int = -2; // 解析失败或越界
pub const FFI_ERR_PANIC: c_int = -3; // 内部 panic 被 catch_unwind 拦下

/// 内部纯安全实现：把端口字符串解析成 u16，失败给出分类原因。
/// 不接触任何裸指针，可被 cargo test 直接测（rlib 形态的意义）。
fn parse_port_inner(bytes: &[u8]) -> Result<u16, c_int> {
    if bytes.is_empty() {
        return Err(FFI_ERR_PARSE);
    }
    let text = std::str::from_utf8(bytes).map_err(|_| FFI_ERR_PARSE)?;
    let port: u16 = text.parse().map_err(|_| FFI_ERR_PARSE)?;
    if port == 0 {
        return Err(FFI_ERR_PARSE); // 端口 0 无意义，作为业务非法输入
    }
    Ok(port)
}

/// 解析端口字符串，成功把结果写入 `*out` 并返回 0。
///
/// # Safety
/// - `ptr`：合法 NUL 结尾 C 字符串或 null；
/// - `out`：非 null 且对齐到 u16、可写，生命周期覆盖本次调用。
#[no_mangle]
pub unsafe extern "C" fn ex03_parse_port(ptr: *const c_char, out: *mut u16) -> c_int {
    // 第 1 层护栏：catch_unwind。闭包里是「理论上不应 panic」的代码，兜住万一。
    let caught = std::panic::catch_unwind(|| {
        if ptr.is_null() || out.is_null() {
            return FFI_ERR_NULL;
        }
        // SAFETY: 调用方保证 ptr 合法（本函数 Safety 文档）。
        let bytes = unsafe { CStr::from_ptr(ptr) }.to_bytes();
        match parse_port_inner(bytes) {
            Ok(port) => {
                // SAFETY: 上面已排除 out.is_null()，且 Safety 文档保证可写。
                unsafe { *out = port };
                FFI_OK
            }
            Err(code) => code,
        }
    });
    caught.unwrap_or(FFI_ERR_PANIC) // panic 在边界内被吞掉，绝不 unwind 进 C
}

/// 【教学性演示】当 trigger != 0 时故意 panic 一次——真实代码里 panic 是 bug，
/// 但边界函数仍应被 catch_unwind 保护，把 panic 翻译成 FFI_ERR_PANIC。
/// 首行注释声明运行前提：这只是演示护栏机制的桩，不应出现在真实产品代码里。
#[no_mangle]
pub extern "C" fn ex03_panic_probe(trigger: c_int) -> c_int {
    let caught = std::panic::catch_unwind(|| {
        if trigger != 0 {
            panic!("ex03 panic_probe: 故意触发的 panic，验证边界护栏"); // 故意的
        }
        FFI_OK
    });
    caught.unwrap_or(FFI_ERR_PANIC)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::CString;

    #[test]
    fn parse_ok_writes_out() {
        let s = CString::new("8080").unwrap();
        let mut out: u16 = 0;
        // SAFETY: s 为合法 NUL 结尾串，out 为可写局部变量。
        let code = unsafe { ex03_parse_port(s.as_ptr(), &mut out) };
        assert_eq!(code, FFI_OK);
        assert_eq!(out, 8080);
    }

    #[test]
    fn parse_fail_keeps_out_untouched() {
        let s = CString::new("not-a-port").unwrap();
        let mut out: u16 = 777;
        // SAFETY: 同上。
        let code = unsafe { ex03_parse_port(s.as_ptr(), &mut out) };
        assert_eq!(code, FFI_ERR_PARSE);
        assert_eq!(out, 777, "失败路径不得写 out");
    }

    #[test]
    fn parse_null_ptr_reports_err_null() {
        // SAFETY: null 输入在函数内被显式检查（返回值 -1）。
        let code = unsafe { ex03_parse_port(std::ptr::null(), std::ptr::null_mut()) };
        assert_eq!(code, FFI_ERR_NULL);
    }

    #[test]
    fn panic_is_translated_to_code_not_unwind() {
        assert_eq!(ex03_panic_probe(0), FFI_OK);
        // catch_unwind 使 panic 不会杀死测试进程
        assert_eq!(ex03_panic_probe(1), FFI_ERR_PANIC);
    }

    #[test]
    fn out_of_range_is_parse_error() {
        let s = CString::new("70000").unwrap(); // 超出 u16
        let mut out: u16 = 0;
        // SAFETY: 同上。
        let code = unsafe { ex03_parse_port(s.as_ptr(), &mut out) };
        assert_eq!(code, FFI_ERR_PARSE);
        assert_eq!(out, 0);
    }
}
