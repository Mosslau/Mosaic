// 修复版（与同目录 error.rs 对照）。两种修法，任选其一：
//  A 从共享引用中取出值 -> 只能复制（clone）；适用「偶尔取一次、代价可接受」的场景；
//  B 由调用方交出所有权（拥有 map），在内部 remove 掉元素 —— 想要 move 就必须真拥有。
// 验证：rustc --edition 2021 fix.rs -o /tmp/c02-hashmap-move-out-fix && /tmp/c02-hashmap-move-out-fix（已验证：rustc 1.92.0 / macOS arm64）。
use std::collections::HashMap;

fn main() {
    // A：共享读 + clone
    let map = HashMap::from([("a".to_string(), "A".to_string())]);
    let v = map["a"].clone(); // 复制一份，原 map 保持不变
    println!("A: {v}，map 还在：len = {}", map.len());

    // B：拥有 map 后 remove —— 真正把值搬走
    let mut owned = HashMap::from([("b".to_string(), "B".to_string())]);
    let v2 = owned.remove("b").unwrap_or_default(); // remove 返回 Option<V>，把元素移出
    println!("B: {v2}，移出后 len = {}", owned.len());
}
