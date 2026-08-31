// 来源：languages/rs/ph10-smart-pointers/exercises/README.md 练习 1
// 说明：用 Box 构建递归链表——enum 递归必须用 Box 打破无限大小（E0072 的解法），
//       实现 len/sum 递归方法，验证 Drop 自动释放整条链。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-01-box-recursive-list.rs -o /tmp/sol01
// 运行：/tmp/sol01
// 验证状态：已验证（编译零警告，输出 len = 4, sum = 10，断言通过）

#[derive(Debug)]
enum List {
    Cons(i32, Box<List>), // Box 让递归合法：List 大小 = 标签 + 指针
    Nil,
}

impl List {
    fn len(&self) -> usize {
        match self {
            List::Cons(_, tail) => 1 + tail.len(),
            List::Nil => 0,
        }
    }

    fn sum(&self) -> i32 {
        match self {
            List::Cons(v, tail) => v + tail.sum(),
            List::Nil => 0,
        }
    }
}

fn main() {
    let list = List::Cons(
        1,
        Box::new(List::Cons(2, Box::new(List::Cons(3, Box::new(List::Cons(4, Box::new(List::Nil))))))),
    );

    let len = list.len();
    let sum = list.sum();
    println!("len = {len}, sum = {sum}");
    assert_eq!((len, sum), (4, 10));

    // main 结束时整条链按「尾部先行」递归释放，无需手写 free——Drop（RAII）的保证
}
