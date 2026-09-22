// exercises/sol-01-entities.rs —— 练习 1 参考实现：定义业务实体结构体
// 来源：languages/rs/ph03-data-structure/exercises/README.md 练习 1
// 验证环境：rustc 1.92.0
// 编译：rustc sol-01-entities.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告，运行无 panic）

#[derive(Debug, Clone)]
struct User {
    id: u32,
    name: String,
    email: String,
}

#[derive(Debug, Clone, PartialEq)]
struct Device {
    id: u32,
    name: String,
    online: bool,
}

#[derive(Debug, Clone, PartialEq)]
struct Order {
    id: u32,
    product: String,
    amount: u32,
}

fn main() {
    let user = User { id: 1, name: String::from("alice"), email: String::from("alice@example.com") };
    let user2 = user.clone(); // Clone：生成副本
    println!("user  #{}: {} <{}>", user.id, user.name, user.email);
    println!("user2 : {:?}", user2);

    let dev = Device { id: 100, name: String::from("sensor-a"), online: true };
    let dev2 = dev.clone();
    assert_eq!(dev, dev2); // PartialEq：== 比较
    println!("device #{}: {} online={}", dev.id, dev.name, dev.online);

    let order = Order { id: 7, product: String::from("widget"), amount: 300 };
    let order2 = order.clone();
    assert_eq!(order, order2);
    println!("order #{}: {} amount={}", order.id, order.product, order.amount);

    println!("all assertions passed");
}
