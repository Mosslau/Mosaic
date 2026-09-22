// exercises/sol-01-order-state.rs —— 练习 1 参考实现：订单状态建模
// 来源：exercises/README.md 练习 1（roadmap 承诺「用 enum 表达订单状态」）
// 验证环境：rustc 1.92.0
// 编译：rustc sol-01-order-state.rs -o /tmp/sol-01-order-state
// 运行：/tmp/sol-01-order-state
// 验证状态：已验证（rustc 1.92.0）

/// 订单状态：每个变体携带该状态特有的数据——非法状态无法表达。
#[derive(Debug, Clone, PartialEq)]
enum OrderState {
    Pending,                              // 已下单，待确认
    Confirmed { by: String },             // 已确认，记录确认人
    Shipped { tracking: String },         // 已发货，携带快递单号
    Delivered,                            // 已送达
    Cancelled { reason: String },         // 已取消，记录原因
}

impl OrderState {
    /// 人类可读描述：match 穷尽覆盖全部五个变体。
    fn describe(&self) -> String {
        match self {
            OrderState::Pending => "已下单，等待确认".to_string(),
            OrderState::Confirmed { by } => format!("已确认，确认人：{}", by),
            OrderState::Shipped { tracking } => format!("已发货，快递单号：{}", tracking),
            OrderState::Delivered => "已送达".to_string(),
            OrderState::Cancelled { reason } => format!("已取消，原因：{}", reason),
        }
    }

    /// 终态判断：matches! + 或模式，一行表达两个变体。
    fn is_final(&self) -> bool {
        matches!(self, OrderState::Delivered | OrderState::Cancelled { .. })
    }
}

fn main() {
    let states = vec![
        OrderState::Pending,
        OrderState::Confirmed { by: "张工".into() },
        OrderState::Shipped { tracking: "SF1234567890".into() },
        OrderState::Delivered,
        OrderState::Cancelled { reason: "用户取消".into() },
    ];
    for s in &states {
        println!("[{}] {}", if s.is_final() { "终态" } else { "进行中" }, s.describe());
    }

    // 断言验证 is_final 行为
    assert_eq!(OrderState::Delivered.is_final(), true);
    assert_eq!(OrderState::Cancelled { reason: "x".into() }.is_final(), true);
    assert_eq!(OrderState::Pending.is_final(), false);
    assert_eq!(OrderState::Confirmed { by: "x".into() }.is_final(), false);
    assert_eq!(OrderState::Shipped { tracking: "x".into() }.is_final(), false);
    println!("\n全部断言通过");
}
