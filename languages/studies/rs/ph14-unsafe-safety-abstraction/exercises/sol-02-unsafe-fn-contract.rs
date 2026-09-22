// 来源：languages/rs/ph14-unsafe-safety-abstraction/exercises/README.md 练习 2
// 说明：unsafe fn 契约 + 边界测试——手写 get_unchecked（无边界检查）并写出 # Safety
//       文档契约，再写安全包装强制契约，最后为抽象补边界测试（正常/首尾/越界/空切片）。
//       对应 roadmap 练习「阅读标准库中的 unsafe 封装示例」（std 的 get_unchecked 即此形态）
//       与「为 unsafe 抽象写边界测试」。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-02-unsafe-fn-contract.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告）
// 验证块（实测输出，rustc 1.92.0 macOS arm64）：
//   1. get_checked 边界测试 5 组全部通过
//   2. unsafe 路径 get_unchecked(data, 2) = 30
//   断言通过

/// 无边界检查的按索引取字节——契约由文档承担，不变量由开发者维护。
///
/// # Safety
/// - `idx` 必须小于 `slice.len()`
/// - 调用方必须保证 `slice` 在调用期间有效（正常借用即可保证）
///
/// 违反上述任一条件即未定义行为（UB）：可能读到越界内存、可能被优化器折叠成任意值。
unsafe fn get_unchecked(slice: &[u8], idx: usize) -> u8 {
    // SAFETY: 调用方已按 # Safety 契约保证 idx < slice.len()
    unsafe { *slice.get_unchecked(idx) }
}

/// 安全包装：在安全侧做边界检查，把「idx 合法」这一不变量变成类型系统可验证的事实；
/// unsafe 只保留「已知合法」的解引用（最小 unsafe 边界）
fn get_checked(slice: &[u8], idx: usize) -> Option<u8> {
    if idx >= slice.len() {
        return None;
    }
    Some(unsafe { get_unchecked(slice, idx) })
}

fn main() {
    let data: &[u8] = &[10, 20, 30, 40];

    // 边界测试：正常/首尾/越界/空切片（5 组）
    assert_eq!(get_checked(data, 0), Some(10)); // 首元素
    assert_eq!(get_checked(data, 3), Some(40)); // 末元素
    assert_eq!(get_checked(data, 4), None); // 越界 → None（不 panic）
    assert_eq!(get_checked(&[], 0), None); // 空切片
    assert_eq!(get_checked(&[], 99), None); // 空切片越界
    println!("1. get_checked 边界测试 5 组全部通过");

    // unsafe 契约路径：调用方保证 idx < len（此处合法，无 UB）
    let v = unsafe { get_unchecked(data, 2) };
    println!("2. unsafe 路径 get_unchecked(data, 2) = {v}");
    println!("断言通过");
}
