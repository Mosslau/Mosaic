// examples/ex04-mut-borrow-nll.rs —— 可变借用与 NLL：引用活到「最后一次使用」
// 验证环境：rustc 1.92.0
// 编译：rustc ex04-mut-borrow-nll.rs -o ex04
// 运行：./ex04
// 已验证：本环境编译零警告，运行输出 before/after 两行结果

/// 把切片第一个元素翻倍
fn double_first(nums: &mut [i32]) {
    if let Some(first) = nums.first_mut() {
        *first *= 2;
    }
}

fn main() {
    let mut values = vec![1, 2, 3, 4];

    let r = &values[0];
    println!("before: {}", r); // r 的最后一次使用，此后 r 失效

    double_first(&mut values); // NLL：r 已失效，可变借用合法
    println!("after: {:?}", values);
}
