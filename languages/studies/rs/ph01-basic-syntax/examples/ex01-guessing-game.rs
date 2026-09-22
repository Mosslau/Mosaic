// examples/ex01-guessing-game.rs —— 猜数字游戏（基础版）：固定答案，循环读取输入并用 match 比较
// 验证环境：rustc 1.92.0
// 编译：rustc ex01-guessing-game.rs -o ex01
// 运行：./ex01   （或管道喂入：echo 42 | ./ex01）
// 已验证：本环境编译零警告，输入 42 输出「猜对了！」，输入非数字输出错误提示

use std::io;

fn main() {
    println!("猜数字（1-100）！");

    let secret = 42; // 固定答案，随机数属于后续阶段（rand crate）的内容

    loop {
        println!("请输入你的猜测：");

        let mut guess = String::new();
        if io::stdin().read_line(&mut guess).is_err() {
            println!("读取输入失败");
            continue;
        }

        // 解析失败（非数字、EOF 空行）给出提示后继续，而不是 panic
        let guess: i32 = match guess.trim().parse() {
            Ok(n) => n,
            Err(_) => {
                println!("请输入数字");
                continue;
            }
        };

        match guess.cmp(&secret) {
            std::cmp::Ordering::Less => println!("太小！"),
            std::cmp::Ordering::Greater => println!("太大！"),
            std::cmp::Ordering::Equal => {
                println!("猜对了！");
                break;
            }
        }
    }
}
