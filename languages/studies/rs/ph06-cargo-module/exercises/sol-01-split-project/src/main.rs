// exercises/sol-01-split-project/src/main.rs —— 练习 1 参考实现：二进制入口
// 拆分自 exercises/ex01-single-source.rs 的 main，行为与单文件版本一致
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 sol-01-split-project/ 目录内执行）
// 运行：cargo run
// 验证状态：已验证（rustc 1.92.0）

use temp_stats::{parser, service};

fn main() {
    let input = "1700000000\tbeijing\t25.5\n1700000100\tshanghai\t28.0\n\
                 1700000200\tbeijing\t26.5\n1700000300\tshanghai\t27.5";
    let records = parser::parse_all(input);
    println!("总记录数: {}", records.len());
    let earliest = records.iter().map(|r| r.ts).min();
    if let Some(ts) = earliest {
        println!("最早时间戳: {}", ts);
    }
    for (city, avg) in service::avg_by_city(&records) {
        println!("{}: {:.1}", city, avg);
    }
}
