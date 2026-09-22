// 来源：languages/rs/ph14-unsafe-safety-abstraction/exercises/README.md 练习 4
// 说明：FFI 调用基础——用 extern "C" 声明并调用 libc 的 strlen / abs / malloc / free，
//       练习 CString/CStr 与「谁分配谁释放」的跨边界内存约定。
//       对应 roadmap 学习内容「FFI 调用基础」（调自建 C 库见 examples/ex06）。
// 验证环境：rustc 1.92.0（macOS arm64；macOS 上 rustc 默认链接 libSystem，libc 函数直接可用），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-04-ffi-libc.rs -o /tmp/sol04
// 运行：/tmp/sol04
// 验证状态：已验证（编译零警告）
// 验证块（实测输出，rustc 1.92.0 macOS arm64）：
//   1. strlen("练习 FFI") = 10
//   2. abs(-7) = 7
//   3. malloc 8 字节写入 1..=8, sum = 36
//   断言通过
//   （"练习 FFI" UTF-8 为 练(3B)+习(3B)+空格(1B)+F(1B)+F(1B)+I(1B) = 10 字节，strlen 不含 '\0'）

use std::ffi::{c_char, c_int, c_void, CString};

// extern "C" 块：声明 C ABI 的外部函数（2021 edition 下 unsafe 前缀可省略）
extern "C" {
    fn strlen(s: *const c_char) -> usize;
    fn abs(i: c_int) -> c_int;
    fn malloc(size: usize) -> *mut c_void;
    fn free(ptr: *mut c_void);
}

fn main() {
    // 1. strlen：CString 以 '\0' 结尾（含内部 '\0' 的字符串会提前截断，需注意）
    let s = CString::new("练习 FFI").unwrap();
    let len = unsafe { strlen(s.as_ptr()) };
    println!("1. strlen(\"练习 FFI\") = {len}");
    assert_eq!(len, 10);

    // 2. abs：C 函数返回值直接使用
    let a = unsafe { abs(-7) };
    println!("2. abs(-7) = {a}");
    assert_eq!(a, 7);

    // 3. malloc/free：手动分配→写入→读取→释放（谁分配谁释放的不变量由开发者维护）
    let p = unsafe { malloc(8) };
    assert!(!p.is_null(), "malloc(8) 不应返回空指针");
    unsafe {
        // 用 from_raw_parts_mut 把裸指针临时包装成切片，方便写入/求和
        let arr = std::slice::from_raw_parts_mut(p as *mut u8, 8);
        arr.copy_from_slice(&[1, 2, 3, 4, 5, 6, 7, 8]);
        let sum: u8 = arr.iter().sum();
        println!("3. malloc 8 字节写入 1..=8, sum = {sum}");
        assert_eq!(sum, 36);
        free(p); // 忘记 free 就是内存泄漏；重复 free 是 UB
    }
    println!("断言通过");
}
