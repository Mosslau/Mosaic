// examples/feat-demo/src/main.rs —— 同一 package 的二进制同样受 features 控制
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 4
// 验证环境：rustc 1.92.0 + cargo 1.92.0，依赖 serde_json 1.0.108（需网络拉取，可选）
// 编译：cargo build（在 examples/feat-demo/ 目录内执行）
// 运行：cargo run（默认含 json）；cargo run --no-default-features（零依赖）；cargo run --features pretty；cargo run --all-features
// 验证状态：已验证（rustc 1.92.0）

use feat_demo::describe;

fn main() {
    println!("{}", describe());
    #[cfg(feature = "json")] // 关掉 json 后本块不编译，也不引用 serde_json
    {
        let pretty = feat_demo::json_util::pretty_print(r#"{"a":1}"#).expect("JSON 应有效");
        println!("{}", pretty);
    }
}
