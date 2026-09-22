// exercises/sol-04-unwrap-redemption.rs —— 练习 4 参考实现：unwrap 灾难现场
// 来源：exercises/README.md 练习 4
// 说明：演示 `Vec::first()` 返回 `Option<&T>`；裸 `unwrap` 在 None 上会 panic，
//       本文件只包含安全改写版本。panic 版本在注释中展示，运行它程序会崩溃（仅供观察）。
// 验证环境：rustc 1.92.0
// 编译：rustc sol-04-unwrap-redemption.rs -o /tmp/sol-04-unwrap-redemption
// 运行：/tmp/sol-04-unwrap-redemption
// 验证状态：已验证（rustc 1.92.0）

fn main() {
    // —— 观察环节（不良风格，勿运行）——
    // let nums: Vec<i32> = vec![];
    // let first = nums.first().unwrap();
    // 运行上面的代码会 panic，消息为：
    //   thread 'main' panicked at ...: called `Option::unwrap()` on a `None` value
    // 关键片段：`Option::unwrap()` 与 `None`——unwrap 在 None 上取不到值直接崩溃。

    // —— 改写一：match 完整处理 Some / None 两条路径，行为完全由你控制 ——
    let nums: Vec<i32> = vec![];
    match nums.first() {
        Some(v) => println!("match: 第一个元素是 {}", v),
        None => println!("match: 列表为空，没有元素"),
    }

    // 有值列表走 Some 分支
    let nums = vec![10, 20];
    match nums.first() {
        Some(v) => println!("match: 第一个元素是 {}", v),
        None => println!("match: 列表为空，没有元素"),
    }

    // —— 改写二：unwrap_or 提供急求值默认值，None 时也不 panic ——
    let empty: Vec<i32> = vec![];
    let default = empty.first().copied().unwrap_or(-1);
    println!("unwrap_or: 空列表取默认值 -> {}", default);

    // —— 改写三：unwrap_or_else 惰性默认值，None 时才执行闭包 ——
    let val = empty.first().copied().unwrap_or_else(|| {
        // 仅在 None 时执行，可以放复杂计算
        42
    });
    println!("unwrap_or_else: 空列表取惰性默认值 -> {}", val);
}
