// 本文件故意编译失败：期望错误码 E0507（cannot move out of index of `HashMap<String, String>`）。
// 本文件头部另有机器可读标记行：// expect-error: E0507（verify.sh 据此断言）。
// 场景：HashMap 的 Index（map[key]）返回的是共享引用 &V；从共享引用后面「拿所有权」被禁止。
//       （与 examples/e06、sol-01 case3 的 Vec 场景同理：借来的数据没有所有权可让渡。）
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0507]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
// expect-error: E0507
use std::collections::HashMap;

fn main() {
    let map = HashMap::from([("a".to_string(), "A".to_string())]);
    let v = map["a"]; // E0507：Index 产出共享引用，不能从其后 move 出 String
    println!("{v}");
}
