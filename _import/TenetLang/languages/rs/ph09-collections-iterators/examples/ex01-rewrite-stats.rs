// 来源：languages/rs/ph09-collections-iterators/09-collections-iterators.md 第 6 章示例 1
// 说明：用迭代器重写 for 循环统计——命令式版本 vs filter+count/sum 版本 vs 单次遍历的 fold 版本
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex01-rewrite-stats.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告，输出符合预期）

fn main() {
    let scores = vec![72, 88, 95, 41, 60, 100, 33];

    // 命令式版本：for 循环 + 可变累加器（mut 是命令式风格的标志）
    let mut pass_count = 0;
    let mut total = 0;
    for &s in &scores {
        if s >= 60 {
            pass_count += 1;
            total += s;
        }
    }
    println!("命令式: 及格 {pass_count} 人, 平均 {:.1}", total as f64 / pass_count as f64);

    // 迭代器版本 1：filter + count / sum（同一谓词写两遍，遍历两次）
    let pass_count2 = scores.iter().filter(|&&s| s >= 60).count();
    let total2: i32 = scores.iter().filter(|&&s| s >= 60).sum();
    println!("迭代器: 及格 {pass_count2} 人, 平均 {:.1}", total2 as f64 / pass_count2 as f64);

    // 迭代器版本 2：一个 fold 同时算两个统计量（只遍历一次）
    // 注意闭包收到的是 &i32（iter() 元素），用 |&s| 解构；filter 收到的是 &&i32，用 |&&s|
    let (cnt, sum) = scores
        .iter()
        .filter(|&&s| s >= 60)
        .fold((0, 0), |(cnt, sum), &s| (cnt + 1, sum + s));
    println!("fold:   及格 {cnt} 人, 平均 {:.1}", sum as f64 / cnt as f64);
}
