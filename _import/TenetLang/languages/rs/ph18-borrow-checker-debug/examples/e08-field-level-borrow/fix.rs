// 修复版（与同目录 error.rs 对照）。两个思路，任选其一：
//  A 调整顺序：让借用的「最后一次使用」先发生，再调用需要 &mut 的方法；
//  B 字段级借用：只借需要的字段 —— 编译器允许对「不重叠」字段同时一读一写（见主文档 3.7）。
// 验证：rustc --edition 2021 fix.rs -o /tmp/e08-field-level-borrow-fix && /tmp/e08-field-level-borrow-fix（已验证：rustc 1.92.0 / macOS arm64）。
struct Stats {
    name: String,
    hits: u64,
}

impl Stats {
    fn hit(&mut self) {
        self.hits += 1;
    }
    fn name_str(&self) -> &str {
        &self.name
    }
}

fn main() {
    // A：先消费借用，再整体可变
    let mut a = Stats { name: "alice".into(), hits: 0 };
    let label_a = a.name_str();
    println!("A: {label_a}"); // 借用收口
    a.hit(); // 允许

    // B：字段级借用 —— 借 &b.name 的同时直接改 b.hits（两个字段不重叠）
    let mut b = Stats { name: "bob".into(), hits: 0 };
    let label_b = &b.name; // 只借字段 name
    b.hits += 1; // 改字段 hits：与上面的借用不冲突
    println!("B: {label_b} hits={}", b.hits);
}
