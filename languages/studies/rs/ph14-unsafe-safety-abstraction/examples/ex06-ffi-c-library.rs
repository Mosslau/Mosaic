// examples/ex06-ffi-c-library.rs —— FFI 调用基础 ②：调用自建 C 库（cc 编译 .dylib + rustc 链接）
// 验证环境：rustc 1.92.0 + Apple clang 21.0.0（macOS arm64），零第三方依赖
// 编译：
//   1. 编译 C 库为动态库（产物到 /tmp，仓库零二进制残留）：
//      cc -shared -fPIC -O2 -o /tmp/libmystrlib.dylib mystrlib.c
//   2. 编译 Rust 并链接（-L 指向库目录；rpath 让运行期无需 DYLD_LIBRARY_PATH）：
//      rustc --edition 2021 -D warnings -L /tmp -l dylib=mystrlib ex06-ffi-c-library.rs \
//           -o /tmp/ex06 -C link-args="-Wl,-rpath,/tmp"
// 运行：/tmp/ex06
// 验证状态：已验证（编译零警告；输出为实测）

use std::ffi::{c_char, CStr};

// #[link(name = "mystrlib")] 告诉链接器找 libmystrlib.dylib（-l dylib=mystrlib）
#[link(name = "mystrlib")]
extern "C" {
    fn add_i32(a: i32, b: i32) -> i32;
    fn mul_u64(a: u64, b: u64) -> u64;
    fn point_len(p: Point2D) -> f64;
    fn greet() -> *const c_char;
}

// 跨 FFI 传结构体：Rust 侧必须 #[repr(C)] 与 C 侧布局一致（深入内存布局属于 ph19）
#[repr(C)]
#[derive(Debug, Clone, Copy)]
struct Point2D {
    x: f64,
    y: f64,
}

fn main() {
    // 基础数值函数
    let s = unsafe { add_i32(3, 4) };
    println!("1. add_i32(3, 4) = {s}");
    let m = unsafe { mul_u64(6, 7) };
    println!("2. mul_u64(6, 7) = {m}");

    // 结构体按值传递（repr(C) 保证布局一致）
    let p = Point2D { x: 3.0, y: 4.0 };
    let l = unsafe { point_len(p) };
    println!("3. point_len(Point2D{{3.0, 4.0}}) = {l}");

    // C 返回字符串指针：用 CStr 借用（不复制），转 &str 需 to_str()
    let g = unsafe { CStr::from_ptr(greet()) };
    println!("4. greet() = {:?}", g.to_str().unwrap());

    // 认知小结：
    // - extern "C" 声明 + #[link] + -l 链接：三步即可调用任意 C 库
    // - C 侧返回值如果是裸指针，跨边界后「谁分配谁释放」由约定决定（greet 返回静态字符串，
    //   不需要 free；若返回 malloc 的内存则调用方负责 free——本示例未涉及，属于 ph23）
}
