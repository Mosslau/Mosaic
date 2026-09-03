// 正面示例（不是错误案例，可通过编译并运行）：演示「两阶段借用」。
// 两阶段只放行「隐式」可变借用；源码里手写的 &mut 永远是普通可变借用（立即激活）。
// 验证：rustc --edition 2021 main.rs && ./main（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    // 1. 方法调用自动引用（autoref）：receiver 的 &mut 先「预留」，参数求值完再「激活」
    let mut v = vec![1, 2, 3];
    v.push(v.len()); // 对 v.len() 的不可变读取发生在 push 的可变借用激活之前
    println!("v = {v:?}"); // [1, 2, 3, 3]

    // 2. 复合赋值运算符（+=）对同一变量先读后写同样被放行
    let mut x = 1;
    x += x;
    println!("x = {x}"); // 2

    // 对比：手写 &mut 不享受两阶段 —— 见 exercises/sol-01 的 E0503 案例：
    // set(&mut n, n) 在同一表达式里既显式可变借用又读取 n，编译失败，需先做快照。
}
