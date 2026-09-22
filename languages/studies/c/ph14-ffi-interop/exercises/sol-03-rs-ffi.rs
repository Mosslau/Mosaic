//! sol-03-rs-ffi.rs —— 参考实现: 用 Rust 调用 C 函数（extern "C" + unsafe）
//!
//! 前置: 先编译题面给定的 leap 动态库（C 源码见练习 1 题面 / sol-01）:
//!   mkdir -p /tmp/ph14-sol03
//!   cc -Wall -Wextra -std=c11 -dynamiclib leap.c -o /tmp/ph14-sol03/libleap.dylib
//! 编译: rustc --edition 2021 -D warnings sol-03-rs-ffi.rs \
//!         -L /tmp/ph14-sol03 -l leap -o /tmp/ph14-sol03/sol03
//! 运行: /tmp/ph14-sol03/sol03
//! 验证环境: rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）
//! 验证状态: 已验证（零警告; 4 条断言全过, 退出码 0; 实测输出见文件尾）
//!
//! 要点:
//!   - `#[link(name = "leap")]` + `-L ... -l leap` 找到 libleap.dylib
//!   - `extern "C"` 块声明 C 链接函数; 调用必须在 unsafe 块内
//!   - 把 C 的错误码（-1）映射成 Rust 的类型化 Result——C 的错误码
//!     不直接泄漏到 Rust 业务代码里

use std::fmt;

const LEAP_OK_LEAP: i32 = 1;
const LEAP_OK_NOT: i32 = 0;
const LEAP_ERR_BADARG: i32 = -1;

#[link(name = "leap")]
extern "C" {
    fn leap_is_leap(year: i32) -> i32;
}

/// 类型化错误：非法年份（C 侧返回 -1）
#[derive(Debug, PartialEq)]
enum LeapError {
    InvalidYear(i32),
}

impl fmt::Display for LeapError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            LeapError::InvalidYear(y) => write!(f, "非法年份: {y}"),
        }
    }
}

/// C 错误码 → Rust Result 的边界映射（本题核心）
fn leap(year: i32) -> Result<bool, LeapError> {
    let rc = unsafe { leap_is_leap(year) };   // 跨语言调用必须在 unsafe 内
    match rc {
        LEAP_OK_LEAP => Ok(true),
        LEAP_OK_NOT => Ok(false),
        LEAP_ERR_BADARG => Err(LeapError::InvalidYear(year)),
        other => unreachable!("leap_is_leap 不应返回 {other}"),
    }
}

fn main() {
    // 4 个用例断言（含错误路径的类型化结果）
    assert_eq!(leap(2000), Ok(true), "2000 应为闰年");
    assert_eq!(leap(1900), Ok(false), "1900 应为非闰年");
    assert_eq!(leap(2024), Ok(true), "2024 应为闰年");
    assert_eq!(leap(0), Err(LeapError::InvalidYear(0)), "0 应为非法参数");

    for (year, want) in [(2000i32, "闰年"), (1900, "非闰年"),
                         (2024, "闰年"), (0, "非法参数")] {
        println!("leap_is_leap({year}) -> {:?}（期望: {want}）",
                 leap(year));
    }
    println!("sol-03: 全部断言通过, 退出码 0");
}

// 实测输出（本机一次运行）：
// leap_is_leap(2000) -> Ok(true)（期望: 闰年）
// leap_is_leap(1900) -> Ok(false)（期望: 非闰年）
// leap_is_leap(2024) -> Ok(true)（期望: 闰年）
// leap_is_leap(0) -> Err(InvalidYear(0))（期望: 非法参数）
// sol-03: 全部断言通过, 退出码 0
