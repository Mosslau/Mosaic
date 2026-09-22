// 来源：languages/rs/ph09-collections-iterators/exercises/README.md 练习 5
// 说明：迭代器与借用冲突——复现 E0502（边遍历边 push），用三种解法修复，不用裸 unwrap
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-05-borrow-conflict.rs -o /tmp/sol05
// 运行：/tmp/sol05
// 验证状态：已验证（编译零警告，输出符合预期）

// 故意不通过编译（E0502）：迭代器持有集合不可变借用期间做结构性修改。
// 运行前提：取消注释后 rustc 报 error[E0502]（cannot borrow `nums` as mutable
// because it is also borrowed as immutable），请勿取消注释指望编译通过。
// let mut nums = vec![1, 2, 3];
// for n in &nums {
//     nums.push(*n); // push 需要可变借用，与循环持有的不可变借用冲突
// }

fn main() {
    let mut nums = vec![1, 2, 3, 4, 5, 6];

    // 解法 1：先收集要加的数据，循环结束后再修改（"算"与"改"分离）
    let extra: Vec<i32> = nums.iter().map(|n| n * 10).collect();
    nums.extend(extra);
    println!("{nums:?}");

    // 解法 2：原地修改每个元素用 iter_mut（可变借用与迭代器共存是允许的）
    for n in nums.iter_mut() {
        *n += 1;
    }
    println!("{nums:?}");

    // 解法 3：按条件删除用 retain（内部封装安全的"边遍历边删"）
    let mut words = vec![String::from("a"), String::from("bb"), String::from("ccc")];
    words.retain(|w| w.len() >= 2);
    println!("{words:?}");
}
