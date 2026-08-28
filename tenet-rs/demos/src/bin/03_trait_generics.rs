// 03 · trait 与泛型演示
// 运行：cargo run --bin 03_trait_generics

trait Shape {
    fn area(&self) -> f64;
}

struct Circle { r: f64 }
struct Square { side: f64 }

impl Shape for Circle {
    fn area(&self) -> f64 {
        3.14159 * self.r * self.r
    }
}

impl Shape for Square {
    fn area(&self) -> f64 {
        self.side * self.side
    }
}

/// 泛型版本：编译期单态化（每种类型生成一份代码，零运行时开销）
fn total_area_generic<T: Shape>(shapes: &[T]) -> f64 {
    shapes.iter().map(|s| s.area()).sum()
}

/// dyn 版本：运行时 vtable 分发（一次间接调用，像 C++ 虚函数）
fn total_area_dyn(shapes: &[Box<dyn Shape>]) -> f64 {
    shapes.iter().map(|s| s.area()).sum()
}

fn main() {
    let circles = vec![Circle { r: 1.0 }, Circle { r: 2.0 }];
    println!("泛型（单态化）: {}", total_area_generic(&circles));

    let mixed: Vec<Box<dyn Shape>> = vec![
        Box::new(Circle { r: 1.0 }),
        Box::new(Square { side: 2.0 }),
    ];
    println!("dyn（vtable）: {}", total_area_dyn(&mixed));
}
