//! sol-01：导出 C 可调用函数（练习 1 参考实现）。
//!
//! 要求回顾：两个导出函数 `gcd` / `lcm`，i64 进出，不 panic；C 侧静态/动态各链一次。
//! 设计说明：`lcm(a, b)` 遇到 0 按「最小公倍数无定义」返回 0——这是**业务约定**
//! 而不是错误，无需错误码；函数体用迭代版欧几里得算法，避免递归过深也天然无 panic。
//! 验证环境：cargo/rustc 1.92.0 + Apple clang 21.0.0（macOS arm64），本机实测「已验证」。

use std::os::raw::c_longlong;

/// 最大公约数（非负）。欧几里得算法迭代版。
#[no_mangle]
pub extern "C" fn gcd(a: c_longlong, b: c_longlong) -> c_longlong {
    let (mut x, mut y) = (a.unsigned_abs(), b.unsigned_abs());
    while y != 0 {
        let r = x % y;
        x = y;
        y = r;
    }
    x as c_longlong // a=b=0 时 gcd 约定为 0（x 初值 0，循环不进）
}

/// 最小公倍数。任一输入为 0 时返回 0（业务约定，见文件头注释）。
/// 用 `a/gcd*b` 避免先乘后除导致的中间溢出（i64 范围内）。
#[no_mangle]
pub extern "C" fn lcm(a: c_longlong, b: c_longlong) -> c_longlong {
    if a == 0 || b == 0 {
        return 0;
    }
    let g = gcd(a, b);
    (a / g) * b
}
