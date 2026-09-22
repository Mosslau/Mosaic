// examples/ex04-tracing-log/src/main.rs —— tracing 结构化诊断教学（主文档 3.7 / 示例 4）
// 验证环境：rustc/cargo 1.92.0（edition 2021）；依赖 tokio 1 / reqwest 0.12(rustls-tls) /
//   tracing 0.1 / tracing-subscriber 0.3(env-filter)，均 crates.io 拉取（可配 rsproxy）；
//   运行时需联网访问 https://example.com
// 编译/运行：cargo build；RUST_LOG=ph17_demo=debug cargo run —— 未在本环境验证
use reqwest::Error;
use tokio::time::{sleep, Duration};
use tracing::{debug, error, info, info_span, instrument};
use tracing_subscriber::EnvFilter;

/// #[instrument]：以函数名自动开一个 span，函数参数进结构化字段
#[instrument]
async fn fetch(url: &str) -> Result<String, Error> {
    info!(url, "sending request"); // 结构化字段：url 作为字段而非拼进文本
    let body = reqwest::get(url).await?.text().await?;
    debug!(bytes = body.len(), "response ok");
    Ok(body)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 订阅者：fmt 输出 + EnvFilter 按 RUST_LOG 过滤（语法与 env_logger 一致）
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info,ph17_demo=debug")),
        )
        .init();

    info!("app started");

    // 手开 span + .instrument：把 span 绑到 future 上，跨 .await 携带上下文
    let span = info_span!("job", job_id = 42);
    let body = fetch("https://example.com").instrument(span).await?;

    // span 已关闭，这里只能单点记录；字段用 ? 走 Debug 输出
    sleep(Duration::from_millis(50)).await;
    error!(?body, len = body.len(), "demo finished（error 级别仅演示字段继承）");
    Ok(())
}
