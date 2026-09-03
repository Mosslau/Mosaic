// 修复版（与同目录 error.rs 对照）。两种思路，任选其一：
//  A 先为数据找好「家」：创建生命周期足够长的拥有变量，再借用它；
//  B 集合改为拥有 String，添加时把值 move/clone 进集合，彻底不存借用。
// 验证：rustc --edition 2021 fix.rs -o /tmp/e07-temporary-lifetime-fix && /tmp/e07-temporary-lifetime-fix（已验证：rustc 1.92.0 / macOS arm64）。
fn main() {
    // A：先建拥有变量再借
    let mut tags: Vec<&str> = Vec::new();
    let hot = String::from("hot"); // hot 活得比 tags 里的借用久
    tags.push(&hot);
    println!("A: {tags:?}");

    // B：集合拥有 String，切掉借用链
    let mut owned_tags: Vec<String> = Vec::new();
    owned_tags.push(String::from("cold")); // 字面量直接 move 进集合
    let another = String::from("warm");
    owned_tags.push(another.clone()); // 还想继续用 another，就 clone 一份进集合
    println!("B: {owned_tags:?}");
}
