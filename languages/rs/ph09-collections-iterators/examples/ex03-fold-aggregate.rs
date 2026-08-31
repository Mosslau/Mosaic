// 来源：languages/rs/ph09-collections-iterators/09-collections-iterators.md 第 6 章示例 3
// 说明：用 fold 实现聚合——一个 fold 同时求最大/最小/个数、fold 构建 HashMap（词频）、sum 只是 fold 的特例
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex03-fold-aggregate.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;

fn main() {
    let nums = [3, 1, 4, 1, 5, 9, 2, 6];

    // 自定义聚合：一个 fold 同时求最大、最小、个数——累加器是三元组
    // 初始值 (i32::MIN, i32::MAX, 0) 决定累加器类型与极值起点
    let (max, min, count) = nums.iter().fold(
        (i32::MIN, i32::MAX, 0),
        |(mx, mn, cnt), &n| (mx.max(n), mn.min(n), cnt + 1),
    );
    println!("max={max} min={min} count={count}");

    // 用 fold 构建 HashMap：词频统计的纯函数式版本
    // 累加器是集合——闭包修改后必须把 acc "还回去"（作为最后一行表达式）
    let words = ["rust", "go", "rust", "c", "rust", "go"];
    let freq: HashMap<&str, u32> = words.iter().fold(HashMap::new(), |mut acc, w| {
        *acc.entry(w).or_insert(0) += 1;
        acc
    });
    println!("{freq:?}"); // {"rust": 3, "go": 2, "c": 1}

    // sum 只是 fold 的特例：fold(0, |acc, n| acc + n)
    let sum_fold = nums.iter().fold(0, |acc, n| acc + n);
    println!("sum via fold: {sum_fold}"); // 31
}
