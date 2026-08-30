// examples/json-cfg/src/main.rs —— 添加第三方 crate 并固定版本（serde_json）
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 3
// 验证环境：rustc 1.92.0 + cargo 1.92.0，依赖 serde 1.0.197 / serde_json =1.0.108（需网络拉取）
// 编译：cargo build（在 examples/json-cfg/ 目录内执行）
// 运行：cargo run
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Deserialize)]
struct Config {
    name: String,
    port: u16,
    tags: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let json = r#"{"name":"svc-a","port":8080,"tags":["rust","storage"]}"#;
    let v: Value = serde_json::from_str(json)?;    // 动态 Value
    println!("name = {}, port = {}", v["name"], v["port"]);
    let cfg: Config = serde_json::from_str(json)?; // 类型化反序列化
    println!("name={} port={} tags={:?}", cfg.name, cfg.port, cfg.tags);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deserialize_config() {
        let json = r#"{"name":"svc-b","port":9090,"tags":[]}"#;
        let cfg: Config = serde_json::from_str(json).expect("应能反序列化");
        assert_eq!(cfg.name, "svc-b");
        assert_eq!(cfg.port, 9090);
        assert!(cfg.tags.is_empty());
    }

    #[test]
    fn dynamic_value_access() {
        let v: Value = serde_json::from_str(r#"{"a":{"b":1}}"#).unwrap();
        assert_eq!(v["a"]["b"], 1);
    }
}
