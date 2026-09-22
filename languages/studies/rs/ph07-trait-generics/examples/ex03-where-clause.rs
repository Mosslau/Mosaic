// 来源：languages/rs/ph07-trait-generics/07-trait-generics.md 第 6 章示例 3
// 说明：where 子句约束复杂泛型——group_and_sum 三组约束 + 泛型结构体 Counter 的 impl 块 where
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc ex03-where-clause.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;
use std::hash::Hash;

// K 可哈希（HashMap key）、V 可拷贝可相加（累加）：三组约束
fn group_and_sum<K, V>(pairs: &[(K, V)]) -> HashMap<K, V>
where
    K: Clone + Eq + Hash,
    V: Copy + Default + std::ops::Add<Output = V>,
{
    let mut acc: HashMap<K, V> = HashMap::new();
    for (k, v) in pairs {
        let entry = acc.entry(k.clone()).or_insert_with(V::default);
        *entry = *entry + *v;
    }
    acc
}

// 泛型结构体：impl 块上的 where 约束
#[derive(Debug)]
struct Counter<K> { counts: HashMap<K, u64> }

impl<K> Counter<K>
where
    K: Eq + Hash,
{
    fn new() -> Self { Counter { counts: HashMap::new() } }
    fn add(&mut self, key: K) { *self.counts.entry(key).or_insert(0) += 1; }
    fn total(&self) -> u64 { self.counts.values().sum() }
}

fn main() {
    let orders = vec![
        (String::from("alice"), 100u32),
        (String::from("bob"), 200),
        (String::from("alice"), 150),
    ];
    println!("totals: {:?}", group_and_sum(&orders));

    let mut c = Counter::new();
    c.add(String::from("INFO"));
    c.add(String::from("WARN"));
    c.add(String::from("INFO"));
    println!("{:?} total={}", c.counts, c.total());
}
