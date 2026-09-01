// 来源：languages/rs/ph14-unsafe-safety-abstraction/exercises/README.md 练习 1
// 说明：把 unsafe 块包在安全函数内——用裸指针 + 指针运算实现求和/最大值/首字节，
//       unsafe 只出现在函数内部的「最小 unsafe 边界」，对外 API 全部安全。
//       对应 roadmap 练习「把 unsafe 块包在安全函数内」。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-01-raw-pointer-safety.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告）
// 验证块（实测输出，rustc 1.92.0 macOS arm64）：
//   1. sum_raw = 150
//   2. max_raw = 50
//   3. first_byte(10) = 10
//   断言通过
//   （sum_raw 对 [10,20,30,40,50] 求和 = 150；max_raw = 50；first_byte 取小端首字节 = 10）

/// 安全 API：用裸指针遍历求和（内部 unsafe 只负责解引用，边界由调用方传 len 保证）
fn sum_raw(ptr: *const i32, len: usize) -> i32 {
    let mut acc = 0;
    for i in 0..len {
        // 最小 unsafe 边界：单条解引用语句，周围逻辑全部安全
        unsafe { acc += *ptr.add(i) };
    }
    acc
}

/// 安全 API：用裸指针求最大值（空输入直接 assert——安全 API 不默默返回垃圾值）
fn max_raw(ptr: *const i32, len: usize) -> i32 {
    assert!(len > 0, "空输入无法取最大值");
    let mut m = unsafe { *ptr }; // 首元素必然存在（len > 0）
    for i in 1..len {
        let v = unsafe { *ptr.add(i) };
        if v > m {
            m = v;
        }
    }
    m
}

/// 安全 API：裸指针按字节视角取首字节（*const i32 → *const u8，位不变）
fn first_byte(ptr: *const i32) -> u8 {
    unsafe { *(ptr as *const u8) }
}

fn main() {
    let arr = [10i32, 20, 30, 40, 50];
    let ptr = arr.as_ptr(); // 创建裸指针是安全操作

    println!("1. sum_raw = {}", sum_raw(ptr, arr.len()));
    println!("2. max_raw = {}", max_raw(ptr, arr.len()));
    println!("3. first_byte(10) = {}", first_byte(ptr));

    // 断言（确定性值）
    assert_eq!(sum_raw(ptr, arr.len()), 150);
    assert_eq!(max_raw(ptr, arr.len()), 50);
    assert_eq!(first_byte(ptr), 10);
    println!("断言通过");
}
