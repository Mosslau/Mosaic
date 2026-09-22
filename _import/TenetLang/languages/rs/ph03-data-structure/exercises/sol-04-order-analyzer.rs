// exercises/sol-04-order-analyzer.rs —— 练习 4 参考实现：订单分析器
// 来源：languages/rs/ph03-data-structure/exercises/README.md 练习 4
// 验证环境：rustc 1.92.0
// 编译：rustc sol-04-order-analyzer.rs -o /tmp/sol04
// 运行：/tmp/sol04
// 验证状态：已验证（编译零警告，断言全部通过）

use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
struct Order {
    product: String,
    amount: u32,
    category: String,
}

#[derive(Debug)]
struct Analysis {
    by_category: HashMap<String, usize>,
    total_by_product: HashMap<String, u32>,
    sorted: Vec<Order>,
}

fn analyze(orders: &[Order]) -> Analysis {
    let mut by_category: HashMap<String, usize> = HashMap::new();
    let mut total_by_product: HashMap<String, u32> = HashMap::new();

    for o in orders {
        // 返回的 Analysis 拥有 HashMap 的 key，需 clone 一份（owned key）
        *by_category.entry(o.category.clone()).or_insert(0) += 1;
        total_by_product
            .entry(o.product.clone())
            .and_modify(|v| *v += o.amount)
            .or_insert(o.amount);
    }

    // 排序需要一份可变副本（不动入参）
    let mut sorted: Vec<Order> = orders.to_vec();
    sorted.sort_by(|a, b| b.amount.cmp(&a.amount));

    Analysis { by_category, total_by_product, sorted }
}

fn main() {
    let orders = vec![
        Order { product: String::from("widget"), amount: 100, category: String::from("hardware") },
        Order { product: String::from("gadget"), amount: 250, category: String::from("electronics") },
        Order { product: String::from("widget"), amount: 150, category: String::from("hardware") },
        Order { product: String::from("thingy"), amount: 300, category: String::from("hardware") },
        Order { product: String::from("gadget"), amount: 80, category: String::from("electronics") },
    ];

    let a = analyze(&orders);

    // 按 category 分组数量：hardware=3, electronics=2
    assert_eq!(a.by_category.get("hardware"), Some(&3));
    assert_eq!(a.by_category.get("electronics"), Some(&2));

    // 按 product 分组总额：widget=250, gadget=330, thingy=300
    assert_eq!(a.total_by_product.get("widget"), Some(&250));
    assert_eq!(a.total_by_product.get("gadget"), Some(&330));
    assert_eq!(a.total_by_product.get("thingy"), Some(&300));

    // 排序：amount 降序 -> thingy(300) > gadget(250) > widget(150) > widget(100) > gadget(80)
    assert_eq!(a.sorted[0].amount, 300);
    assert_eq!(a.sorted[1].amount, 250);
    assert_eq!(a.sorted[4].amount, 80);

    println!("analysis: {:?}", a);
    println!("all assertions passed");
}
