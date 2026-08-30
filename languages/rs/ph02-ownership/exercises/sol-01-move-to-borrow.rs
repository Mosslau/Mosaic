// exercises/sol-01-move-to-borrow.rs —— 练习 1 参考解：move 改借用
// 验证环境：rustc 1.92.0
// 编译：rustc sol-01-move-to-borrow.rs -o sol01
// 运行：./sol01
// 已验证：本环境编译零警告，输出大写串、长度、以及调用后仍可用的原始 text

// 参数改为 &str：只借用，不夺取 ownership；返回值仍是新 String
fn shout(s: &str) -> String {
    s.to_uppercase()
}

// 纯只读借用，连返回值都不需要拥有
fn len_of(s: &str) -> usize {
    s.len()
}

fn main() {
    let text = String::from("rust ownership");

    let loud = shout(&text); // 借用 text，text 保留 ownership
    let n = len_of(&text); // 再次借用

    println!("shout: {}", loud);
    println!("len: {}", n);
    println!("text still usable: {}", text); // 改动前这里会报 E0382
}
