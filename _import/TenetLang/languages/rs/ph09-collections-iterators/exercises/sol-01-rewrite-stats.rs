// 来源：languages/rs/ph09-collections-iterators/exercises/README.md 练习 1
// 说明：用迭代器重写 for 循环统计——命令式版本保留为注释对照，迭代器版本两个（filter+count/sum、单次 fold）
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-01-rewrite-stats.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告，输出符合预期）

fn main() {
    let scores = vec![72, 88, 95, 41, 60, 100, 33];

    // 命令式版本（对照）：for 循环 + 可变累加器
    // let mut pass_count = 0;
    // let mut total = 0;
    // for &s in &scores { if s >= 60 { pass_count += 1; total += s; } }

    // 版本 1：filter + count / sum（谓词收到 &&i32，用 |&&s| 解构）
    let pass_count: usize = scores.iter().filter(|&&s| s >= 60).count();
    let total: i32 = scores.iter().filter(|&&s| s >= 60).sum();

    // 版本 2：一个 fold 同时算两个统计量（只遍历一次，累加器是 (人数, 总分) 元组）
    let (cnt, sum) = scores
        .iter()
        .filter(|&&s| s >= 60)
        .fold((0, 0), |(cnt, sum), &s| (cnt + 1, sum + s));

    // 两个迭代器版本结果一致：及格 5 人（72/88/95/60/100），总分 415
    assert_eq!((pass_count, total), (cnt, sum));
    println!("及格 {cnt} 人, 平均 {:.1}", sum as f64 / cnt as f64);
}
