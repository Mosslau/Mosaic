// 来源：languages/rs/ph07-trait-generics/07-trait-generics.md 第 6 章示例 2
// 说明：把重复的 max_score / max_ts 改造成一个泛型函数 max_of，再用 max_by_key 与 sum 演示 trait bound 的组合
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc ex02-generic-fn.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告，输出符合预期）

// 改造前：fn max_score(scores: &[u32]) -> Option<u32> { scores.iter().copied().max() }
//          fn max_ts(timestamps: &[u64]) -> Option<u64> { timestamps.iter().copied().max() }
// 改造后：一个泛型函数，T: Ord + Copy 覆盖所有"可全序比较可拷贝"类型
fn max_of<T: Ord + Copy>(items: &[T]) -> Option<T> {
    items.iter().copied().max()
}

// max_by_key：按 key 取最大元素（key 由调用方传入；T: Clone 以便返回 owned 值）
fn max_by_key<T: Clone, K: Ord>(items: &[T], key: impl Fn(&T) -> K) -> Option<T> {
    items.iter().max_by(|a, b| key(a).cmp(&key(b))).cloned()
}

// 泛型统计：sum 适用于任何"有默认值 + 可拷贝 + 可相加"的数值类型
fn sum<T: Default + Copy + std::ops::Add<Output = T>>(items: &[T]) -> T {
    let mut total = T::default();
    for &item in items { total = total + item; }
    total
}

fn main() {
    let scores = [85u32, 92, 78, 95];
    println!("max: {}", max_of(&scores).expect("scores 非空"));
    println!("sum: {}", sum(&scores));
    println!("avg: {:.2}", sum(&scores) as f64 / scores.len() as f64);

    let words = ["rust", "go", "c", "python"];
    // Reverse 反转比较：取"最短"的那个
    println!("shortest: {}", max_by_key(&words, |w| std::cmp::Reverse(w.len())).expect("words 非空"));
}
