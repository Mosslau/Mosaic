// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 8
// 说明：serde + toml——TOML 配置文件解析（嵌套表 → 嵌套结构体）、序列化回 TOML。
//       TOML 是 Rust 生态配置的主流格式（Cargo.toml 就是 TOML）。
// 验证环境：rustc 1.92.0（macOS arm64）；serde 1.0.229 + toml 1.1.4（rsproxy 拉取）
// 构建：cd examples/crates && CARGO_TARGET_DIR=/tmp/ph13-target cargo run --release --bin ex08-serde-toml
// 验证状态：已验证（serde 1.0.229 / toml 1.1.4；输出为实测）

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug)]
struct AppConfig {
    name: String,
    debug: bool,
    server: ServerSection, // 嵌套表 [server]
    tags: Vec<String>,     // 数组
}

#[derive(Serialize, Deserialize, Debug)]
struct ServerSection {
    host: String,
    port: u16,
}

const CONFIG_TOML: &str = r#"
name = "log-forwarder"
debug = true
tags = ["prod", "cn-east"]

[server]
host = "127.0.0.1"
port = 9000
"#;

fn main() {
    // ===== 1. 解析 TOML → 结构体 =====
    let cfg: AppConfig = toml::from_str(CONFIG_TOML).expect("解析应成功");
    println!("1. 解析结果: {cfg:?}");
    assert_eq!(cfg.server.port, 9000);
    assert_eq!(cfg.tags.len(), 2);

    // ===== 2. 结构体 → TOML 字符串 =====
    let out = toml::to_string_pretty(&cfg).expect("序列化不会失败");
    println!("2. 序列化回 TOML:\n{out}");

    // ===== 3. 类型不匹配的错误消息 =====
    let bad = "name = 123\ndebug = true\n[server]\nhost = \"x\"\nport = 1\n";
    match toml::from_str::<AppConfig>(bad) {
        Ok(_) => println!("3. 意外成功"),
        Err(e) => println!("3. 类型错误: {}", e.message()), // 只取首行消息
    }
}
