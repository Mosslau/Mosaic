// exercises/sol-04-feature-control/src/main.rs —— 练习 4 参考实现：feature 范围控制 + cfg 配合
// 验证环境：rustc/cargo 1.92.0（edition 2021）；依赖见 Cargo.toml（crates.io 拉取，可配 rsproxy）。
// 编译/运行：cargo build / cargo run（运行需联网访问 https://httpbin.org/json）—— 编译已验证（cargo 1.92.0 本机实测 cargo build 通过）；运行需联网，未在本环境验证
use serde::Deserialize;

// cfg(feature) 与 feature 的配合：编译期常量判断决定这段代码是否参与编译
#[derive(Debug, Deserialize)]
struct Payload {
    slideshow: serde_json::Value,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // reqwest 的 rustls-tls feature 已开：此处使用 TLS 请求走纯 Rust 实现，无 OpenSSL 系统依赖
    let resp = reqwest::get("https://httpbin.org/json").await?;
    let payload: Payload = resp.json().await?;
    println!("slideshow title = {:?}", payload.slideshow);

    // 演示 cfg(feature) 双路径：编译时按 feature 选择实现（本工程未开 demo-extra，走默认分支）
    #[cfg(feature = "demo-extra")]
    println!("extra demo feature enabled");

    #[cfg(not(feature = "demo-extra"))]
    println!("extra demo feature disabled（默认分支）");

    Ok(())
}
