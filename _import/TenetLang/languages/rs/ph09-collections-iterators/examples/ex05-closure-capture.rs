// 来源：languages/rs/ph09-collections-iterators/09-collections-iterators.md 第 6 章示例 5
// 说明：闭包捕获三种模式（Fn/FnMut/FnOnce）——用三个泛型函数把 trait 约束"钉死"，观察编译行为
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex05-closure-capture.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告，输出符合预期）

// 三个泛型函数把三种闭包 trait 约束"钉死"：
fn run_once<F: FnOnce() -> String>(f: F) -> String {
    f()
} // 可 move 出捕获值，只能调用一次
fn run_mut<F: FnMut()>(mut f: F) {
    f();
    f();
} // 可改捕获变量，可多次调用
fn run_fn<F: Fn() -> u32>(f: F) -> u32 {
    f() + f()
} // 只读捕获，可多次调用

fn main() {
    // FnOnce：|| tag2 按值捕获——调用后 tag2 的所有权被移出（意外移动的现场）
    let tag2 = String::from("v2");
    let moved = run_once(|| tag2);
    // println!("{tag2}"); // 故意不通过编译（E0382）：use of moved value——tag2 已被 move 出，请勿取消注释
    println!("{moved}");

    // FnMut：计数器闭包被调用两次，内部可变捕获生效
    let mut counter = 0;
    run_mut(|| counter += 1);
    println!("counter = {counter}"); // 2

    // Fn：只读闭包；Fn ⊆ FnMut ⊆ FnOnce，所以也能传给 run_once
    let base = 100;
    println!("run_fn: {}", run_fn(|| base + 1));      // (101) + (101) = 202
    println!("run_once: {}", run_once(|| format!("tag-{base}"))); // 借用捕获也满足 FnOnce
    println!("base = {base}");                        // 只借用，未移动
}
