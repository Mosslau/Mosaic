// examples/ex01-three-structs.rs —— 三种结构体 + derive(Debug/Clone/PartialEq)
// 来源：languages/rs/ph03-data-structure/03-data-structure.md 第 6 章「示例 1」
// 验证环境：rustc 1.92.0
// 编译：rustc ex01-three-structs.rs -o /tmp/ex01-three-structs
// 运行：/tmp/ex01-three-structs
// 验证状态：已验证（编译零警告，输出符合预期）

// named field struct：字段命名清晰，最常用
#[derive(Debug, Clone, PartialEq)]
struct Order {
    id: u32,
    product: String,
    quantity: u32,
}

// tuple struct：字段无名、按位置访问，适合包装单值
#[derive(Debug)]
struct Celsius(f64);

// unit struct：无字段，用作标记类型
#[derive(Debug, PartialEq)]
struct Initialized;

fn main() {
    let o1 = Order { id: 1, product: String::from("widget"), quantity: 5 };
    let o2 = o1.clone(); // Clone：生成副本，o1 仍可用
    assert_eq!(o1, o2); // PartialEq：== 比较

    // 字段访问：显式读三个字段（也避免 dead_code 警告）
    println!("order #{}: {} x {}", o1.id, o1.product, o1.quantity);

    let temp = Celsius(36.8);
    println!("temp: {:?} -> {:.1}C", temp, temp.0);

    let state = Initialized;
    assert_eq!(state, Initialized);
    println!("state: {:?}", state);
}
