// exercises/sol-04-feature-flag/src/main.rs —— 练习 4 参考实现：同一 package 的二进制受 features 控制
// 验证环境：rustc 1.92.0 + cargo 1.92.0，serde_json 1.0.108（可选，需网络拉取）
// 编译：cargo build（在 sol-04-feature-flag/ 目录内执行）
// 运行：cargo run；cargo run --no-default-features；cargo run --features json；cargo run --all-features
// 验证状态：已验证（rustc 1.92.0）

use fmt_out::format_table;

fn main() {
    let rows = vec![
        ("disk".to_string(), 80),
        ("cpu".to_string(), 12),
        ("mem".to_string(), 55),
    ];
    #[cfg(feature = "json")] // 关掉 json 后本块不编译，也不引用 serde_json
    {
        let json = fmt_out::format_json(&rows).expect("JSON 序列化不应失败");
        println!("{json}");
        return;
    }
    // 未启用 json 特性时走文本表格输出
    print!("{}", format_table(&rows));
}
