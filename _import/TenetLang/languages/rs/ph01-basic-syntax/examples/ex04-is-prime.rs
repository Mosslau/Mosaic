// examples/ex04-is-prime.rs —— 素数判断：while 循环试除到 √n，打印 1~100 全部素数
// 验证环境：rustc 1.92.0
// 编译：rustc ex04-is-prime.rs -o ex04
// 运行：./ex04
// 已验证：本环境编译零警告，输出以 2 3 5 7 11 开头、以 97 结尾共 25 个素数

fn is_prime(n: u32) -> bool {
    if n < 2 {
        return false;
    }
    let mut i = 2;
    while i * i <= n {
        if n % i == 0 {
            return false;
        }
        i += 1;
    }
    true
}

fn main() {
    print!("1-100 的素数: ");
    for i in 1..=100 {
        if is_prime(i) {
            print!("{} ", i);
        }
    }
    println!();
}
