// examples/ex05-ffi-libc.rs —— FFI 调用基础 ①：用 extern "C" 声明并调用 libc 函数
// 验证环境：rustc 1.92.0（macOS arm64；macOS 上 rustc 默认链接 libSystem，libc 函数直接可用；
//           Linux 上同样可用），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex05-ffi-libc.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告；输出为实测）

use std::ffi::{c_char, c_int, c_void, CString};

// extern "C" 块：声明 C ABI 的外部函数。
// 注意：2021 edition 下可以不写 unsafe 前缀（1.82 起可选）；2024 edition 必须写 `unsafe extern "C"`。
extern "C" {
    fn strlen(s: *const c_char) -> usize;
    fn malloc(size: usize) -> *mut c_void;
    fn free(ptr: *mut c_void);
    fn abs(i: c_int) -> c_int;
}

fn main() {
    // strlen：传 C 字符串指针（CString 以 '\0' 结尾，CStr::as_ptr 返回 *const c_char）
    let s = CString::new("hello").unwrap(); // 内部含 '\0'，跨 FFI 边界不会截断
    let len = unsafe { strlen(s.as_ptr()) };
    println!("1. strlen(\"hello\") = {len}");

    // malloc/free：手动分配与释放——「谁分配谁释放」的不变量由开发者维护
    //（深入的所有权跨边界规则属于 ph23 Rust FFI 与跨语言接口设计阶段）
    let p = unsafe { malloc(16) };
    assert!(!p.is_null(), "malloc(16) 不应返回空指针");
    unsafe {
        std::ptr::write_bytes(p as *mut u8, 0xAB, 16); // 写入 16 字节
        let first = *(p as *const u8); // 读回首字节
        println!("2. malloc(16) 后首字节 = 0x{first:02X}");
        free(p); // 释放——忘记 free 就是内存泄漏
    }

    // abs：C 函数返回值直接使用
    let a = unsafe { abs(-42) };
    println!("3. abs(-42) = {a}");

    // 认知小结：
    // - 调用 extern 函数必须位于 unsafe 上下文（E0133 实测见 ex04 同族演示）
    // - C 函数不报告错误：strlen 假定字符串合法、malloc 失败返回 null——错误约定由 C 库文档定义，
    //   与 Rust 的 Result 体系完全不同（错误处理工程化见 ph11 错误处理与工程质量阶段）
    // - 本示例只演示「调用」，不演示「导出 Rust 函数给 C」与 bindgen/cbindgen（属于 ph23）
}
