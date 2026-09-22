//! mini-kv-service 可执行入口。
//!
//! 环境变量：`KV_PORT`（默认 8090）、`KV_DATA`（默认 `$TMPDIR/mini-kv-service-data`）。
//! 数据目录可跨进程复用：重启后 WAL 重放即恢复（崩溃恢复验收点）。

use mini_kv_service::{api, AppState};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let port: u16 = std::env::var("KV_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8090);
    let data_dir = std::env::var("KV_DATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::temp_dir().join(format!("mini-kv-service-data-{}", std::process::id()))
        });
    let state = AppState::open(data_dir.clone())?;
    println!("mini-kv-service 数据目录：{}", data_dir.display());
    let app = api::router(state);
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", port)).await?;
    println!("mini-kv-service 监听 http://127.0.0.1:{port}（/healthz /kv/* /tools/call /metrics /audit）");
    axum::serve(listener, app).await?;
    Ok(())
}
