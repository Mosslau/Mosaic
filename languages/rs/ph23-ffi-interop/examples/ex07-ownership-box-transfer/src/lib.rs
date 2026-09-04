//! ex07：所有权与内存释放规则跨边界 —— Box 指针在 Rust↔C 之间的往返转移。
//!
//! 教学要点（对应主文档 3.6/3.7/4.3）：
//! - 大块缓冲区跨边界最常见的载体不是逐字节拷贝，而是**转移堆分配的所有权**：
//!   `Vec::into_boxed_slice()` 压缩掉多余的容量元数据后 `Box::into_raw` 交出裸指针，
//!   C 侧持有期间它就是一块「C 眼中的普通内存」。
//! - **谁分配谁释放**：Rust 分配的内存必须回到 Rust 侧用 `Box::from_raw` 收回再 drop；
//!   绝不能让 C 用 `free()` 释放 Rust 分配器出的指针（本机默认分配器虽与 malloc 同源，
//!   但这是可替换的实现细节——Rust 允许换 `#[global_allocator]`，见主文档 4.3。
//!   规则层面「谁分配谁释放」永远是红线，不依赖分配器巧合）。
//! - **长度必须与指针一起传递**：裸指针不带长度信息；对 `Box<[T]>` 调 `into_raw`
//!   得到的是胖指针，`as *mut f64` 后长度元数据就丢了。vec/slice 跨边界的协议是
//!   `ptr + len` 分离传递（主文档 3.7），回收时用 `from_raw_parts_mut` 重建。
//!
//! 教学场景：Rust 分配 f64 缓冲 → C 写入数据 → 调回 Rust 校验求和 → 归还 Rust 释放。
//!
//! 验证环境：cargo/rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）；本机实测「已验证」。

use std::os::raw::c_int;

/// Rust 侧分配一个长度为 `len` 的 f64 缓冲（初值 = 各元素下标），返回裸指针并把
/// 所有权移交给调用方；调用方必须用 `ex07_free(ptr, len)` 归还。失败返回 null。
#[no_mangle]
pub extern "C" fn ex07_allocate(len: c_int) -> *mut f64 {
    if len <= 0 {
        return std::ptr::null_mut();
    }
    let n = len as usize;
    let v: Vec<f64> = (0..n).map(|i| i as f64).collect();
    let boxed: Box<[f64]> = v.into_boxed_slice();
    Box::into_raw(boxed) as *mut f64 // 移交所有权：此后 Rust 不再触碰
}

/// 读取（可能已被 C 改写过的）缓冲并求和返回。
/// 此刻 Rust 只有裸指针，`slice::from_raw_parts` 依据调用方给的 len 重建视图——
/// len 撒谎 = UB，所以协议把 len 当作与指针同等重要的安全前提。
///
/// # Safety
/// - `ptr` 必须来自 `ex07_allocate(len)`，且本次调用前未被 `ex07_free`。
#[no_mangle]
pub unsafe extern "C" fn ex07_sum(ptr: *const f64, len: c_int) -> f64 {
    if ptr.is_null() || len <= 0 {
        return 0.0;
    }
    // SAFETY: 调用方保证 (ptr, len) 与 ex07_allocate 的分配一致（本函数 Safety 文档）。
    let slice = unsafe { std::slice::from_raw_parts(ptr, len as usize) };
    slice.iter().sum()
}

/// 收回所有权并释放——`ex07_allocate` 的唯一合法归还通道（必须与 len 成对）。
///
/// # Safety
/// - `ptr` 必须来自 `ex07_allocate(len)`，`len` 与分配时一致，且所有权尚未转移过。
#[no_mangle]
pub unsafe extern "C" fn ex07_free(ptr: *mut f64, len: c_int) {
    if ptr.is_null() || len <= 0 {
        return;
    }
    // SAFETY: 调用方保证 (ptr, len) 对应一次尚未归还的 ex07_allocate 分配——
    // 此处是唯一 owner，重建 Box<[f64]> 后立即 drop，走 Rust 分配器规则回收。
    let slice = unsafe { std::slice::from_raw_parts_mut(ptr, len as usize) };
    drop(unsafe { Box::from_raw(slice) });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allocate_then_sum_matches_expected() {
        let len = 1000;
        // SAFETY: ptr 来自 ex07_allocate，len 一致，测试内保证先 sum 后 free。
        let ptr = ex07_allocate(len);
        assert!(!ptr.is_null());
        let s = unsafe { ex07_sum(ptr, len) };
        assert_eq!(s, (0..1000).sum::<usize>() as f64);
        // SAFETY: 归还同一 (ptr, len)。
        unsafe { ex07_free(ptr, len) };
    }

    #[test]
    fn zero_or_negative_length_allocation_returns_null() {
        assert!(ex07_allocate(0).is_null());
        assert!(ex07_allocate(-5).is_null());
    }

    #[test]
    fn values_written_by_c_side_are_seen_by_rust() {
        // 模拟 C 侧行为：拿到指针后绕过 Rust 类型系统直接写内存（等价于 C 解引用赋值）
        let len = 8;
        // SAFETY: 同上。
        let ptr = ex07_allocate(len);
        unsafe {
            let slice = std::slice::from_raw_parts_mut(ptr, len as usize);
            for v in slice.iter_mut() {
                *v = 42.0;
            }
        }
        // SAFETY: (ptr, len) 一致。
        let s = unsafe { ex07_sum(ptr, len) };
        assert_eq!(s, 42.0 * 8.0);
        // SAFETY: 归还。
        unsafe { ex07_free(ptr, len) };
    }
}
