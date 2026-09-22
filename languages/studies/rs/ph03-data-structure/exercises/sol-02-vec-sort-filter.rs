// exercises/sol-02-vec-sort-filter.rs —— 练习 2 参考实现：Vec 排序过滤
// 来源：languages/rs/ph03-data-structure/exercises/README.md 练习 2
// 验证环境：rustc 1.92.0
// 编译：rustc sol-02-vec-sort-filter.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告，输出符合预期）

#[derive(Debug)]
struct Order {
    id: u32,
    product: String,
    amount: u32,
    shipped: bool,
}

fn main() {
    let mut orders = vec![
        Order { id: 1, product: String::from("widget"), amount: 100, shipped: true },
        Order { id: 2, product: String::from("gadget"), amount: 250, shipped: false },
        Order { id: 3, product: String::from("widget"), amount: 150, shipped: false },
        Order { id: 4, product: String::from("thingy"), amount: 300, shipped: true },
        Order { id: 5, product: String::from("gadget"), amount: 80, shipped: false },
    ];

    // 1. 可变借用遍历：所有订单 amount +10（模拟涨价/运费）
    for o in &mut orders {
        o.amount += 10;
    }

    // 2. 按 amount 降序排序
    orders.sort_by(|a, b| b.amount.cmp(&a.amount));
    println!("sorted:");
    for o in &orders {
        println!("  #{} {} amount={} shipped={}", o.id, o.product, o.amount, o.shipped);
    }

    // 3. 过滤未发货订单（借用，不动 orders）
    let pending: Vec<&Order> = orders.iter().filter(|o| !o.shipped).collect();
    println!("pending (shipped == false): {:?}", pending);
}
