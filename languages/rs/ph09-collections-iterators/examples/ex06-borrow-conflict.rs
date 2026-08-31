// 来源：languages/rs/ph09-collections-iterators/09-collections-iterators.md 3.8 小节与第 6 章示例 6
// 说明：迭代器与借用冲突（E0502）——复现"边遍历边改集合"，给出三种安全解法
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex06-borrow-conflict.rs -o /tmp/ex06
// 运行：/tmp/ex06
// 验证状态：已验证（编译零警告，输出符合预期）

// ===== 故意不通过编译（E0502），请勿取消注释 =====
// 运行前提：以下代码取消注释后无法通过 rustc 编译，报 error[E0502]:
// "cannot borrow `nums` as mutable because it is also borrowed as immutable"。
// 想看真实报错请复制到独立文件执行 rustc --edition 2021，不要指望本文件编译通过。
// let mut nums = vec![1, 2, 3];
// for n in &nums {          // &nums 不可变借用贯穿整个循环（迭代器持有借用）
//     nums.push(*n);        // push 需要可变借用——与已存在的不可变借用冲突
// }

fn main() {
    let mut nums = vec![1, 2, 3, 4, 5, 6];

    // 方案 1：先收集要加的数据，循环结束后再修改（把"算"和"改"分成两步）
    let extra: Vec<i32> = nums.iter().map(|n| n * 10).collect();
    nums.extend(extra);
    println!("{nums:?}"); // [1, 2, 3, 4, 5, 6, 10, 20, 30, 40, 50, 60]

    // 方案 2：原地修改每个元素用 iter_mut（可变借用与迭代器共存是允许的）
    for n in nums.iter_mut() {
        *n += 1;
    }
    println!("{nums:?}"); // [2, 3, 4, 5, 6, 7, 11, 21, 31, 41, 51, 61]

    // 方案 3：按条件删除用 retain（内部封装了安全的"边遍历边删"）
    let mut words = vec![String::from("a"), String::from("bb"), String::from("ccc")];
    words.retain(|w| w.len() >= 2);
    println!("{words:?}"); // ["bb", "ccc"]
}
