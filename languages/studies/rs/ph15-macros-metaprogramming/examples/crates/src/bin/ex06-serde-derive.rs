// examples/crates/src/bin/ex06-serde-derive.rs —— serde derive 实测：derive 生成序列化代码 + #[serde] 属性
// 验证环境：rustc 1.92.0（macOS arm64）；serde 1.0.229 + serde_json 1.0.151（rsproxy 拉取，Cargo.lock 锁定）
// 编译/运行（在 examples/crates 目录）：
//   CARGO_TARGET_DIR=/tmp/ph15-examples-target cargo run --bin ex06-serde-derive
// 验证状态：已验证（编译零警告；输出为实测）

use serde::{Deserialize, Serialize};

// 结构体级属性 rename_all = "camelCase"：所有字段的 JSON 名按 camelCase 转换
// （user_name -> userName；另有 snake_case / kebab-case / PascalCase 等，见主文档 3.5 表格）
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ServerConfig {
    host: String,
    port: u16,
    max_connections: u32,
    // 字段级属性：default（缺字段时用 Default::default()）+ skip_serializing_if
    // （值为 None 时序列化不输出该字段）
    #[serde(default, skip_serializing_if = "Option::is_none")]
    tls_cert: Option<String>,
}

fn main() {
    // 1. 序列化：字段顺序按结构体声明顺序输出（derive 生成代码的确定性可断言）
    let cfg = ServerConfig {
        host: "127.0.0.1".into(),
        port: 8080,
        max_connections: 512,
        tls_cert: Some("cert-a".into()),
    };
    let json = serde_json::to_string(&cfg).unwrap();
    println!("1. 序列化（tls_cert = Some）: {json}");
    assert_eq!(
        json,
        r#"{"host":"127.0.0.1","port":8080,"maxConnections":512,"tlsCert":"cert-a"}"#
    );

    // 2. tls_cert = None：skip_serializing_if 让它不出现
    let cfg2 = ServerConfig {
        tls_cert: None,
        ..cfg.clone()
    };
    let json2 = serde_json::to_string(&cfg2).unwrap();
    println!("2. 序列化（tls_cert = None，被跳过）: {json2}");
    assert_eq!(json2, r#"{"host":"127.0.0.1","port":8080,"maxConnections":512}"#);

    // 3. 反序列化往返：JSON -> 结构体 -> JSON 内容不变
    let back: ServerConfig = serde_json::from_str(&json).unwrap();
    println!("3. 反序列化往返一致 = {}", back == cfg);
    assert_eq!(back, cfg);

    // 4. 缺 tlsCert 字段：Option + default 让反序列化成功
    let json3 = r#"{"host":"10.0.0.2","port":9000,"maxConnections":64}"#;
    let cfg3: ServerConfig = serde_json::from_str(json3).unwrap();
    println!("4. 缺失 tlsCert 反序列化成功: tls_cert = {:?}", cfg3.tls_cert);

    // 5. 类型错误：port 给了字符串 -> serde_json 报错并带行列号（derive 生成的解析逻辑实测）
    let err = serde_json::from_str::<ServerConfig>(
        r#"{"host":"x","port":"oops","maxConnections":1}"#,
    );
    println!("5. 类型错误消息: {}", err.unwrap_err());
}
