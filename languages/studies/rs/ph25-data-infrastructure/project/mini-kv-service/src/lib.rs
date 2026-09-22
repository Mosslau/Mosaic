//! mini-kv-service —— ph25 收官工程「Mini LSM-KV + Axum HTTP + Agent 工具 API」库入口。

pub mod api;
pub mod engine;

pub use api::AppState;
pub use engine::Engine;
