//! sol-04：不透明句柄模式（练习 4 参考实现）。
//!
//! 要求回顾：句柄方法（new/push/get/len/destroy），错误码表达失败，null 句柄不崩溃，
//! destroy 是唯一归还通道。
//!
//! 教学点：
//! - `VecStore` 字段不 `pub`、不 `#[repr(C)]`——对 C 而言它就是「不透明指针」，
//!   C 不能也不该知道内部布局（`sizeof` 它没有意义，也不能 `free()` 它）；
//! - **谁分配谁释放的接口化**：句柄由 `vecstore_new` 产生、只能由 `vecstore_destroy`
//!   归还，能力被锁死在两个函数里，C 侧没有第二种释放途径可犯错；
//! - **错误码纪律**（对照 ex03）：越界/空句柄都是「预期内失败」，用返回码表达而非 panic。
//!
//! unsafe 边界最小化：裸指针只在 `extern "C"` shim 里出现；判空在最外层，
//! 通过句柄访问内部一律先在 shim 里转回 `&mut VecStore`。
//! 验证环境：cargo/rustc 1.92.0 + Apple clang 21.0.0（macOS arm64），本机实测「已验证」。

use std::os::raw::{c_double, c_int, c_longlong};
use std::ptr;

/// 错误码契约（与 C 侧 main.c 的宏保持一致）。
pub const VS_OK: c_int = 0;
pub const VS_ERR_NULL: c_int = -1; // 句柄为 null
pub const VS_ERR_IDX: c_int = -2; // 下标越界

/// 不透明句柄的载体。字段不公开、不加 repr(C)：
/// C 侧只能持有 `*mut VecStore` 并按函数契约使用，无法触达内部。
pub struct VecStore {
    data: Vec<f64>,
}

/// 建一个空句柄；内部分配失败（如 Vec 扩容 panic）由 catch_unwind 兜底转成 null。
/// 失败统一返回 null——C 侧用「句柄是否为空」判断，无需读错误码。
#[no_mangle]
pub extern "C" fn vecstore_new() -> *mut VecStore {
    let result =
        std::panic::catch_unwind(|| Box::into_raw(Box::new(VecStore { data: Vec::new() })));
    result.unwrap_or(ptr::null_mut())
}

/// 追加一个值。成功 0；句柄为 null 返回 -1。
/// 注：真实库的每个边界函数都应收进 catch_unwind 护栏（ex03 的纪律）；
/// 此处为聚焦「句柄模式」省略护栏，教学性简化（L1 覆盖条款）。
///
/// # Safety
/// `h` 必须来自 `vecstore_new` 且尚未被 destroy（或为 null，函数内判空返回错误码）。
#[no_mangle]
pub unsafe extern "C" fn vecstore_push(h: *mut VecStore, v: c_double) -> c_int {
    // SAFETY: 调用方保证 h 来自 vecstore_new 且尚未 destroy（或为 null，这里先判空）。
    let store = match unsafe { h.as_mut() } {
        Some(s) => s,
        None => return VS_ERR_NULL,
    };
    store.data.push(v);
    VS_OK
}

/// 读回第 i 个元素，写入 `*out`。越界返回 -2 且不写 out；null 返回 -1。
///
/// # Safety
/// - `h` 同上；`out` 必须非 null 且可写。
#[no_mangle]
pub unsafe extern "C" fn vecstore_get(
    h: *mut VecStore,
    i: c_longlong,
    out: *mut c_double,
) -> c_int {
    // SAFETY: 调用方保证 h 与 out 满足上述前提。
    let store = match unsafe { h.as_ref() } {
        Some(s) => s,
        None => return VS_ERR_NULL,
    };
    if out.is_null() {
        return VS_ERR_NULL;
    }
    let idx = usize::try_from(i).unwrap_or(usize::MAX); // 负数下标 → 必越界
    match store.data.get(idx) {
        Some(v) => {
            // SAFETY: 上面已排除 out.is_null()。
            unsafe { *out = *v };
            VS_OK
        }
        None => VS_ERR_IDX,
    }
}

/// 返回元素个数；null 句柄返回 -1。
///
/// # Safety
/// `h` 必须来自 `vecstore_new` 且尚未被 destroy（或为 null，函数内返回 -1）。
#[no_mangle]
pub unsafe extern "C" fn vecstore_len(h: *mut VecStore) -> c_longlong {
    // SAFETY: 调用方保证 h 来自 vecstore_new 且未 destroy。
    match unsafe { h.as_ref() } {
        Some(s) => s.data.len() as c_longlong,
        None => -1,
    }
}

/// 归还句柄——唯一合法销毁通道。null 安全（no-op）。
///
/// # Safety
/// `h` 必须来自 `vecstore_new` 且尚未被 destroy 过。
#[no_mangle]
pub unsafe extern "C" fn vecstore_destroy(h: *mut VecStore) {
    if h.is_null() {
        return;
    }
    // SAFETY: 调用方保证 h 来自 Box::into_raw（vecstore_new）且未 destroy——
    // 此处收回所有权并 drop，Vec 与堆内存按 Rust 分配器规则释放。
    drop(unsafe { Box::from_raw(h) });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn with_store<F: FnOnce(*mut VecStore)>(f: F) {
        // SAFETY: 测试内保证：句柄来自 vecstore_new，并在闭包结束后 destroy 一次。
        let h = vecstore_new();
        assert!(!h.is_null());
        f(h);
        // SAFETY: h 未重复归还。
        unsafe { vecstore_destroy(h) };
    }

    #[test]
    fn push_get_roundtrip() {
        with_store(|h| {
            for i in 0..5 {
                // SAFETY: h 有效。
                assert_eq!(unsafe { vecstore_push(h, i as f64) }, VS_OK);
            }
            // SAFETY: h 有效。
            assert_eq!(unsafe { vecstore_len(h) }, 5);
            let mut v = -1.0;
            // SAFETY: h 有效，v 可写。
            assert_eq!(unsafe { vecstore_get(h, 3, &mut v) }, VS_OK);
            assert_eq!(v, 3.0);
        });
    }

    #[test]
    fn get_out_of_range_is_error_and_leaves_out() {
        with_store(|h| {
            // SAFETY: h 有效。
            assert_eq!(unsafe { vecstore_push(h, 42.0) }, VS_OK);
            let mut v = -1.0;
            // SAFETY: h 有效，v 可写。
            assert_eq!(unsafe { vecstore_get(h, 5, &mut v) }, VS_ERR_IDX);
            assert_eq!(v, -1.0, "越界不得写 out");
            // 负数下标同样越界
            // SAFETY: 同上。
            assert_eq!(unsafe { vecstore_get(h, -1, &mut v) }, VS_ERR_IDX);
        });
    }

    #[test]
    fn null_handle_is_reported_not_crash() {
        // SAFETY: 传入 null 是契约允许的失败输入。
        assert_eq!(unsafe { vecstore_push(ptr::null_mut(), 1.0) }, VS_ERR_NULL);
        // SAFETY: 同上。
        assert_eq!(unsafe { vecstore_len(ptr::null_mut()) }, -1);
        let mut v = 0.0;
        // SAFETY: h=null 时函数在写 out 前返回。
        assert_eq!(
            unsafe { vecstore_get(ptr::null_mut(), 0, &mut v) },
            VS_ERR_NULL
        );
        assert_eq!(v, 0.0);
        // SAFETY: destroy(null) 是 no-op。
        unsafe { vecstore_destroy(ptr::null_mut()) };
    }
}
