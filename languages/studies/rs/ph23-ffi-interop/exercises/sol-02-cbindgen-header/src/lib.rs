//! sol-02：用 cbindgen 生成头文件（练习 2 参考实现）。
//!
//! 要求回顾：`#[repr(C)]` 的 `Fraction` + `fraction_add`，cbindgen 生成头文件，
//! C 侧 include 头文件计算 1/2 + 1/3。
//! 教学点：这里的每段 doc 注释都会被 cbindgen 原样搬进 .h——
//! 先写对 Rust 侧注释，头文件文档就有了。
//! 验证环境：cargo/rustc 1.92.0 + cbindgen 0.27.0 + Apple clang 21.0.0，本机实测「已验证」。

use std::os::raw::c_longlong;

/// 有理数 `num / den`。`#[repr(C)]` 让字段布局与 C 结构体一致，
/// 因此它能按值穿过 `extern "C"` 边界。练习要求不做约分。
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct Fraction {
    pub num: c_longlong,
    pub den: c_longlong,
}

/// 分数相加：`a.num/b.den + b.num/b.den`，结果不约分。
/// 若分母为 0，返回 {num:0, den:0} 作为「无定义」标记（业务约定，不 panic）。
#[no_mangle]
pub extern "C" fn fraction_add(a: Fraction, b: Fraction) -> Fraction {
    if a.den == 0 || b.den == 0 {
        return Fraction { num: 0, den: 0 };
    }
    let num = a.num * b.den + b.num * a.den;
    let den = a.den * b.den;
    Fraction { num, den }
}
