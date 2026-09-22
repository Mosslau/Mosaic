// examples/ex04-hashmap-group.rs —— HashMap entry API 分组统计
// 来源：languages/rs/ph03-data-structure/03-data-structure.md 第 6 章「示例 4」
// 验证环境：rustc 1.92.0
// 编译：rustc ex04-hashmap-group.rs -o /tmp/ex04-hashmap-group
// 运行：/tmp/ex04-hashmap-group
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;

fn main() {
    let orders = vec![
        ("alice", 100),
        ("bob", 200),
        ("alice", 150),
        ("carol", 300),
        ("bob", 50),
    ];

    // 按客户累计金额：and_modify 更新已有值，or_insert 插入新键
    let mut total: HashMap<&str, u32> = HashMap::new();
    for (name, amount) in &orders {
        total.entry(name).and_modify(|v| *v += amount).or_insert(*amount);
    }
    println!("totals: {:?}", total);

    // 按客户计数：or_insert(0) 插入默认值，再解引用 +1
    let mut count: HashMap<&str, u32> = HashMap::new();
    for (name, _) in &orders {
        *count.entry(name).or_insert(0) += 1;
    }
    println!("counts: {:?}", count);
}
