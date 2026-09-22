//! ex01：热点函数库（path 依赖，LTO 的实验对象）。
//!
//! 放在独立 crate 里的意义：cargo 默认（release、lto=false、codegen-units=16）
//! 下，rustc 只优化自己编译的那部分——它**看不到**本 crate 内部，跨 crate 的
//! `mix` 调用保持真实函数调用边界。开启 lto 后，链接期优化才让 main 所在 crate
//! 把这里的函数体看穿、内联。于是「同一份源码」在三种 profile 下的运行时间差异，
//! 就是 LTO 的净收益。
//!
//! 函数体刻意极简（一次乘法 + 一次轮转，~3 cycle）：让**跨 crate 调用开销**
//! 成为每轮迭代的主导成本——无 LTO 时每次调用付 call/ret 代价，LTO 后调用被
//! 消除，差异才显形。

/// 对输入做单步混淆（乘法 + 轮转）。工作极小，调用边界是主要成本。
pub fn mix(v: u64) -> u64 {
    v.wrapping_mul(0x9e37_79b9_7f4a_7c15)
        .rotate_left(23)
        .wrapping_add(0x1234_5678_9abc_def0)
}
