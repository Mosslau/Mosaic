// 修复版（与同目录 error.rs 对照）。练习 2 的参考实现，覆盖两种合法修法：
//  修法 A：把「读尾部」与「写容器」彻底分成两个阶段 —— 所有对 tail 的读取都放在 push 之前；
//  修法 B：push 之后还想保留尾部内容，就把尾部复制成拥有的 Vec —— 切掉对原容器的借用。
// 验证：rustc --edition 2021 fix.rs && ./fix（已验证：rustc 1.92.0 / macOS arm64）。

/// A：先算完、打印完，再 push（借用最后一次使用在 push 之前，收口于函数体内）。
fn append_tail_sum_a(items: &mut Vec<u32>, n: usize) {
    let len = items.len();
    let tail: &[u32] = &items[len - n..]; // 借用区间开始
    let sum: u32 = tail.iter().sum();
    println!("A: 尾部 {tail:?} 之和 {sum}"); // 借用最后一次使用在这里结束
    items.push(sum); // 借用已收口，&mut 畅通
}

/// B：需要「push 之后还能读这段内容」，就拥有化 —— to_vec 复制出独立数据。
fn append_tail_sum_b(items: &mut Vec<u32>, n: usize) {
    let len = items.len();
    let tail_owned: Vec<u32> = items[len - n..].to_vec(); // 拥有副本，无借用残留
    let sum: u32 = tail_owned.iter().sum();
    items.push(sum); // 容器随便改
    println!("B: 尾部 {tail_owned:?} 之和 {sum}"); // 读的是副本，不依赖原容器
}

fn main() {
    let mut data_a = vec![1, 2, 3, 4];
    append_tail_sum_a(&mut data_a, 2);
    println!("data_a = {data_a:?}");

    let mut data_b = vec![1, 2, 3, 4];
    append_tail_sum_b(&mut data_b, 2);
    println!("data_b = {data_b:?}");
}
