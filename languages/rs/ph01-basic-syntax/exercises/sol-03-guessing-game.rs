// exercises/sol-03-guessing-game.rs —— 猜数字游戏：loop + match + 解析失败不 panic
// 验证环境：rustc 1.92.0
// 编译：rustc sol-03-guessing-game.rs -o sol03
// 运行：./sol03   （或管道喂入：echo 42 | ./sol03）
// 已验证：本环境编译零警告；输入 42 输出「猜对了！」；输入 abc 提示且不崩溃

use std::cmp::Ordering;
use std::io;

fn main() {
    println!("猜数字（1-100）！");

    let secret = 42; // 固定答案；随机数属于后续阶段（rand crate）

    loop {
        println!("请输入你的猜测：");

        let mut guess = String::new();
        if io::stdin().read_line(&mut guess).is_err() {
            println!("读取输入失败");
            continue;
        }

        // 解析失败提示后继续，不 panic——用 match 处理 Result
        let guess: i32 = match guess.trim().parse() {
            Ok(n) => n,
            Err(_) => {
                println!("请输入数字");
                continue;
            }
        };

        match guess.cmp(&secret) {
            Ordering::Less => println!("太小！"),
            Ordering::Greater => println!("太大！"),
            Ordering::Equal => {
                println!("猜对了！");
                break;
            }
        }
    }
}
