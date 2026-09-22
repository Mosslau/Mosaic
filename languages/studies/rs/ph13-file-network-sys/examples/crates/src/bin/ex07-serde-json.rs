// 来源：languages/rs/ph13-file-network-sys/13-file-network-sys.md 第 6 章示例 7
// 说明：serde + serde_json——derive 宏自动实现 Serialize/Deserialize、结构体 ↔ JSON
//       字符串互转、#[serde] 字段属性（rename/default）、解析错误的行列定位。
// 验证环境：rustc 1.92.0（macOS arm64）；serde 1.0.229 + serde_json 1.0.151（rsproxy 拉取）
// 构建：cd examples/crates && CARGO_TARGET_DIR=/tmp/ph13-target cargo run --release --bin ex07-serde-json
// 验证状态：已验证（serde 1.0.229 / serde_json 1.0.151；JSON 输出与错误消息为实测）

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, PartialEq)]
struct ServerConfig {
    // #[serde] 属性在字段上定制（反）序列化行为
    #[serde(rename = "host_name")] // JSON 里的键名与字段名不同
    host: String,
    port: u16,
    #[serde(default = "default_workers")] // 缺省时用函数给默认值
    workers: u32,
    #[serde(default)] // 缺省时用 Default::default()（bool → false）
    tls: bool,
}

fn default_workers() -> u32 {
    4
}

fn main() {
    // ===== 1. 序列化：结构体 → JSON 字符串 =====
    let cfg = ServerConfig {
        host: "0.0.0.0".to_string(),
        port: 8080,
        workers: 8,
        tls: true,
    };
    let json = serde_json::to_string_pretty(&cfg).expect("序列化不会失败");
    println!("1. 序列化结果:\n{json}");

    // ===== 2. 反序列化：JSON 字符串 → 结构体 =====
    let text = r#"{ "host_name": "127.0.0.1", "port": 9000 }"#; // 缺 workers/tls
    let parsed: ServerConfig = serde_json::from_str(text).expect("解析应成功");
    println!("2. 反序列化: {parsed:?}（workers/tls 用了 default）");
    assert_eq!(parsed.workers, 4); // default_workers()
    assert!(!parsed.tls); // Default for bool

    // ===== 3. 解析错误：serde_json 给出行列定位 =====
    let bad = r#"{ "host_name": "x", "port": "not-a-number" }"#;
    match serde_json::from_str::<ServerConfig>(bad) {
        Ok(_) => println!("3. 意外成功"),
        Err(e) => println!("3. 解析错误: {e}"), // 含行列号
    }

    // ===== 4. 往返一致：serialize ∘ deserialize = 恒等 =====
    let round: ServerConfig = serde_json::from_str(&serde_json::to_string(&cfg).unwrap()).unwrap();
    assert_eq!(cfg, round);
    println!("4. 往返一致断言通过");
}
