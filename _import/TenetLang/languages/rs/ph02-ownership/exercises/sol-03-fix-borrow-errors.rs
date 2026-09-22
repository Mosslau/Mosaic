// exercises/sol-03-fix-borrow-errors.rs —— 练习 3 参考解：修复 E0382 与 E0502
// 验证环境：rustc 1.92.0
// 编译：rustc sol-03-fix-borrow-errors.rs -o sol03
// 运行：./sol03
// 已验证：本环境编译零警告，输出两行预期结果

fn main() {
    // 错误 A 修复：E0382 borrow of moved value
    // 原代码 `let t = s;` 把 s move 走，之后 println 再用 s 报错。
    // 修复：t 改为借用 s，不转移 ownership。
    let s = String::from("ownership");
    let t = &s;
    println!("{} {}", s, t);

    // 错误 B 修复：E0502 cannot borrow as mutable while immutable borrow active
    // 原代码 first = &v[0] 活跃期间执行 v.push(4)，违反 xor 规则。
    // 修复：把 first 的使用提前到 push 之前（NLL 下 first 最后一次使用后即失效），
    // 再把值保存下来供后面打印——不需要复制 v 本身。
    let mut v = vec![1, 2, 3];
    let first = v[0]; // i32 是 Copy，这里直接取值，借用立刻结束
    v.push(4);
    println!("{} {:?}", first, v);
}
