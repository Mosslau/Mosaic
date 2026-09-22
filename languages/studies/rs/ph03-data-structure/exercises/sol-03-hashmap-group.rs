// exercises/sol-03-hashmap-group.rs —— 练习 3 参考实现：HashMap 分组统计
// 来源：languages/rs/ph03-data-structure/exercises/README.md 练习 3
// 验证环境：rustc 1.92.0
// 编译：rustc sol-03-hashmap-group.rs -o /tmp/sol03
// 运行：/tmp/sol03
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;

#[derive(Debug, Clone)]
struct Order {
    product: String,
    amount: u32,
    category: String,
}

fn main() {
    let orders = vec![
        Order { product: String::from("widget"), amount: 100, category: String::from("hardware") },
        Order { product: String::from("gadget"), amount: 250, category: String::from("electronics") },
        Order { product: String::from("widget"), amount: 150, category: String::from("hardware") },
        Order { product: String::from("thingy"), amount: 300, category: String::from("hardware") },
        Order { product: String::from("gadget"), amount: 80, category: String::from("electronics") },
    ];

    // 按 product 分组统计总金额：借用 key（&String 自动 deref 成 &str），无 clone
    let mut total_by_product: HashMap<&str, u32> = HashMap::new();
    for o in &orders {
        total_by_product
            .entry(&o.product)
            .and_modify(|v| *v += o.amount)
            .or_insert(o.amount);
    }
    println!("total by product: {:?}", total_by_product);

    // 按 category 分组统计订单数量：or_insert(0) 插入默认值，再解引用 +1
    let mut count_by_category: HashMap<&str, u32> = HashMap::new();
    for o in &orders {
        *count_by_category.entry(&o.category).or_insert(0) += 1;
    }
    println!("count by category: {:?}", count_by_category);
}
