// exercises/sol-05-order-state-machine.rs —— 练习 5 参考实现：订单状态机迁移表
// 来源：exercises/README.md 练习 5
// 验证环境：rustc 1.92.0
// 编译：rustc sol-05-order-state-machine.rs -o /tmp/sol-05-order-state-machine
// 运行：/tmp/sol-05-order-state-machine
// 验证状态：已验证（rustc 1.92.0）

/// 订单状态（无数据变体）：非法迁移由 transition 在运行时拒绝。
#[derive(Debug, Clone, Copy, PartialEq)]
enum OrderState {
    Pending,
    Confirmed,
    Shipped,
    Delivered,
    Cancelled,
}

impl OrderState {
    /// 状态机迁移：合法迁移表之外一律 Err。
    ///
    /// matches! + 或模式把合法迁移表写成一个表达式——
    /// `(当前状态, 目标状态)` 是当前状态的引用，`&next` 借用目标，
    /// 匹配通过引用自动解出，无需解引用变量。
    fn transition(&self, next: OrderState) -> Result<OrderState, String> {
        let allowed = matches!(
            (self, &next),
            (OrderState::Pending, OrderState::Confirmed | OrderState::Cancelled)
                | (OrderState::Confirmed, OrderState::Shipped | OrderState::Cancelled)
                | (OrderState::Shipped, OrderState::Delivered)
        );
        if allowed {
            Ok(next)
        } else {
            Err(format!("不允许从 {:?} 迁移到 {:?}", self, next))
        }
    }
}

fn main() {
    // 完整链路：Pending → Confirmed → Shipped → Delivered
    let mut order = OrderState::Pending;
    let steps = [OrderState::Confirmed, OrderState::Shipped, OrderState::Delivered];
    for next in steps {
        match order.transition(next) {
            Ok(state) => {
                println!("{:?} -> {:?} 成功", order, state);
                order = state;
            }
            Err(e) => {
                println!("迁移失败: {}", e);
                break;
            }
        }
    }

    // 非法迁移演示一：终态不能再迁移
    match order.transition(OrderState::Cancelled) {
        Err(e) => println!("非法迁移: {}", e),
        Ok(state) => println!("意外成功: {:?}", state),
    }

    // 非法迁移演示二：跳过确认直接送达
    match OrderState::Pending.transition(OrderState::Delivered) {
        Err(e) => println!("非法迁移: {}", e),
        Ok(state) => println!("意外成功: {:?}", state),
    }
}
