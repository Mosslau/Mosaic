// 修复版（与同目录 error.rs 对照）。
// 思路：把「读」提前成独立语句，先快照出 Copy 副本，再发起显式 &mut —— 借用不再重叠。
// 说明：真正需要「一边改容器、一边读它」的写法大多可用两阶段（方法调用/复合赋值），
//       但显式 &mut 场景只能靠拆分语句或快照来消除重叠。
// 验证：rustc --edition 2021 fix.rs && ./fix（已验证：rustc 1.92.0 / macOS arm64）。
fn set(a: &mut i32, b: i32) {
    *a = b;
}

fn main() {
    let mut x = 1;
    let snapshot = x; // 先读：取出 i32 的 Copy 副本
    set(&mut x, snapshot); // 再写：此时没有活跃的读取
    println!("{x}"); // 2
}
