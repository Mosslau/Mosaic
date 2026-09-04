//! ex05 的 Rust 库：要被 cbindgen 生成 C 头文件的「导出面」。
//!
//! 教学要点（对应主文档 3.9）：
//! - cbindgen 能导出的只有 **ABI 稳定类型**：整数/浮点、`#[repr(C)]` 结构体与 enum、
//!   `#[no_mangle] pub extern "C"` 函数。`String`/`Vec`/`Result` 在头文件里没有对应物，
//!   会导出失败或被跳过。
//! - doc 注释会被 cbindgen 原样搬进生成的头文件——「头文件即文档」从写 Rust 侧注释就开始了。
//! - `cbindgen.toml`（同目录）控制语言（C 还是 C++）、头文件风格等。
//!
//! 验证环境：cargo/rustc 1.92.0 + cbindgen 0.27.0 + Apple clang 21.0.0；本机实测「已验证」。

use std::os::raw::{c_char, c_double};

/// 一个可跨边界的点。`#[repr(C)]` 保证字段偏移/对齐与 C 结构体一致（主文档 3.4/4.1），
/// 于是「按值传递结构体」在 ABI 上与 C 完全等价。
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct Point2D {
    pub x: c_double,
    pub y: c_double,
}

/// C 可读的枚举：`#[repr(C)]` 使每个判言在 ABI 上就是普通整数（C 的 enum 等价物）。
/// cbindgen 会把它翻译成 C 的 `typedef enum`。
#[repr(C)]
#[derive(Clone, Copy, PartialEq, Debug)]
pub enum Quadrant {
    Origin = 0,
    Q1 = 1,
    Q2 = 2,
    Q3 = 3,
    Q4 = 4,
}

/// 计算两个点的欧氏距离。
/// 这段 doc 注释会原样出现在生成的头文件里——头文件文档由此而来。
#[no_mangle]
pub extern "C" fn ex05_distance(a: Point2D, b: Point2D) -> c_double {
    let dx = a.x - b.x;
    let dy = a.y - b.y;
    (dx * dx + dy * dy).sqrt()
}

/// 判断点落在哪个象限。约定：坐标轴上的点按「右/上优先」归入相邻象限
/// （原点返回 Origin）。NaN 参与比较按 false 处理，不追求数学完备——演示用。
#[no_mangle]
pub extern "C" fn ex05_quadrant(p: Point2D) -> Quadrant {
    if p.x == 0.0 && p.y == 0.0 {
        return Quadrant::Origin;
    }
    if p.y >= 0.0 {
        if p.x >= 0.0 {
            Quadrant::Q1
        } else {
            Quadrant::Q2
        }
    } else if p.x >= 0.0 {
        Quadrant::Q4
    } else {
        Quadrant::Q3
    }
}

/// 返回永不释放的静态标识串：C 侧只读展示、不负责释放（`c"..."` 静态 CStr 的 as_ptr）。
#[no_mangle]
pub extern "C" fn ex05_tag() -> *const c_char {
    c"ex05-rust-lib".as_ptr()
}
