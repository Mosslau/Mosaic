// 来源：languages/rs/ph10-smart-pointers/examples/ —— 主文档第 6 章示例 1
// 说明：Box 堆分配与递归类型：不用 Box 时 enum List 大小无限（E0072，已验证），
//       用 Box<List> 后每个 Cons 只多一个指针宽度，递归合法，Drop 自动释放整条链。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex01-box-recursive-list.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告，输出符合预期）

#[derive(Debug)]
enum List {
    Cons(i32, Box<List>), // Box 打破递归：List 的大小变为「标签 + 指针」，有限
    Nil,
}

impl List {
    /// 链表长度：递归求值（Cons = 1 + 尾部长度）
    fn len(&self) -> usize {
        match self {
            List::Cons(_, tail) => 1 + tail.len(),
            List::Nil => 0,
        }
    }

    /// 链表元素和：递归求和
    fn sum(&self) -> i32 {
        match self {
            List::Cons(v, tail) => v + tail.sum(),
            List::Nil => 0,
        }
    }
}

fn main() {
    // 堆上分配一串：1 -> 2 -> 3 -> Nil，每个 Box 指向堆上下一节
    let list = List::Cons(
        1,
        Box::new(List::Cons(2, Box::new(List::Cons(3, Box::new(List::Nil))))),
    );

    println!("{list:?}");                      // Cons(1, Cons(2, Cons(3, Nil)))
    println!("len = {}, sum = {}", list.len(), list.sum()); // len = 3, sum = 6

    // 整条链的所有权归 list 一人所有，main 结束时 Box 从尾部开始递归释放，无需手写 free
    // 对比 C 手写链表「遍历 free + 断链」的样板——这是 Drop（RAII）带来的差异
}
