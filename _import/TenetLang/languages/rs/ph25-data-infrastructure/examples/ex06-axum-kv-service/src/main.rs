//! ph25 ex06：Axum 暴露 KV / range-scan HTTP 服务（网络依赖示例）
//!
//! 把 ex02 的「SSTable 单文件读取」换成本阶段服务面的主角：一个内存 KV +
//! range-scan 的 HTTP API（GET/PUT/DELETE /kv/{key}，GET /kv?start=&end=），
//! 演示 Axum 服务端四件事：路由与状态共享（`State<Arc<Mutex<_>>>`）、统一 JSON
//! 错误响应（自定义 `ApiError` + `IntoResponse`）、路径/查询参数抽取、超时语义
//! 落点提示（单机内存 KV 无慢 I/O，超时由调用方/中间件承担——见主文档 3.7）。
//! KV 语义与 ex01~ex04 完全一致（字节 key，有序可 scan）；内存表是 ph18/ph21
//! 所有权与并发纪律的落地（`Arc<Mutex<BTreeMap>>`），真磁盘版本是 project/ 的事。
//!
//! # 验证环境与命令
//! - 验证环境：rustc/cargo 1.92.0（macOS arm64）；依赖需联网拉取（axum 0.8.9 /
//!   tokio 1.53 / serde 1.0 等，本机实测解析版本见 examples/README）
//! - 测试：`cargo test --release`（内存表语义单测 + 路由层 HTTP 冒烟测试）
//! - 运行：`cargo run --release`（默认 127.0.0.1:8090，可用 `KV_PORT=9000` 覆盖）
//! - 冒烟：见 examples/README 的 curl 序列
//! - 质量：`cargo fmt --check && cargo clippy --all-targets -- -D warnings`
//! - 验证状态：**已验证**（2026-09-04 本机实测；curl 冒烟输出见 README）

use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex, MutexGuard};

/// 内存 KV：字节 key 的有序表（scan 语义：start..=end 闭区间有序返回）。
#[derive(Debug, Default)]
struct Kv {
    inner: BTreeMap<Vec<u8>, Vec<u8>>,
}

impl Kv {
    fn get(&self, key: &[u8]) -> Option<&[u8]> {
        self.inner.get(key).map(Vec::as_slice)
    }

    fn put(&mut self, key: Vec<u8>, value: Vec<u8>) {
        self.inner.insert(key, value);
    }

    fn delete(&mut self, key: &[u8]) -> bool {
        self.inner.remove(key).is_some()
    }

    fn scan(&self, start: &[u8], end: &[u8]) -> Vec<(Vec<u8>, Vec<u8>)> {
        self.inner
            .range(start.to_vec()..=end.to_vec())
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect()
    }
}

/// 进程级共享状态：Axum 的 `State` 按请求克隆，锁保证跨请求的写互斥。
#[derive(Clone)]
struct AppState {
    store: Arc<Mutex<Kv>>,
}

fn lock_kv(state: &AppState) -> Result<MutexGuard<'_, Kv>, ApiError> {
    state
        .store
        .lock()
        .map_err(|_| ApiError::internal("kv 锁中毒：某 handler 在持锁时 panic 了"))
}

/// 统一 JSON 错误：NotFound → 404、Internal → 500，body 都是 `{"error": "…"}`。
#[derive(Debug)]
enum ApiError {
    NotFound(String),
    Internal(String),
}

impl ApiError {
    fn not_found(key: &str) -> ApiError {
        ApiError::NotFound(format!("key '{key}' 不存在"))
    }

    fn internal(msg: impl Into<String>) -> ApiError {
        ApiError::Internal(msg.into())
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, msg) = match self {
            ApiError::NotFound(m) => (StatusCode::NOT_FOUND, m),
            ApiError::Internal(m) => (StatusCode::INTERNAL_SERVER_ERROR, m),
        };
        (status, Json(json!({ "error": msg }))).into_response()
    }
}

fn key_lossy(k: &[u8]) -> String {
    String::from_utf8_lossy(k).into_owned()
}

/// GET /kv/{key}
async fn get_kv(
    State(state): State<AppState>,
    Path(key): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let kv = lock_kv(&state)?;
    let raw = key.clone().into_bytes();
    match kv.get(&raw) {
        Some(v) => Ok(Json(json!({ "key": key, "value": key_lossy(v) }))),
        None => Err(ApiError::not_found(&key)),
    }
}

/// PUT /kv/{key}，body：`{"value": "…"}`
async fn put_kv(
    State(state): State<AppState>,
    Path(key): Path<String>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    let value = body
        .get("value")
        .and_then(Value::as_str)
        .ok_or_else(|| ApiError::internal("body 需要 JSON 字符串字段 \"value\""))?;
    let mut kv = lock_kv(&state)?;
    kv.put(key.clone().into_bytes(), value.as_bytes().to_vec());
    Ok(Json(json!({ "key": key, "value": value, "written": true })))
}

/// DELETE /kv/{key}
async fn delete_kv(
    State(state): State<AppState>,
    Path(key): Path<String>,
) -> Result<StatusCode, ApiError> {
    let mut kv = lock_kv(&state)?;
    if kv.delete(key.as_bytes()) {
        Ok(StatusCode::NO_CONTENT)
    } else {
        Err(ApiError::not_found(&key))
    }
}

#[derive(Debug, Deserialize)]
struct ScanQuery {
    start: Option<String>,
    end: Option<String>,
}

/// GET /kv?start=…&end=…（闭区间 range scan；不带参数则扫全表）
async fn scan_kv(
    State(state): State<AppState>,
    Query(q): Query<ScanQuery>,
) -> Result<Json<Value>, ApiError> {
    let kv = lock_kv(&state)?;
    let start = q.start.unwrap_or_default().into_bytes();
    let end = q.end.unwrap_or_default().into_bytes();
    // 参数都缺省时扫全表：用 BTreeMap 首/尾 key 兜底
    let (lo, hi) = if start.is_empty() && end.is_empty() {
        match (kv.inner.first_key_value(), kv.inner.last_key_value()) {
            (Some((f, _)), Some((l, _))) => (f.clone(), l.clone()),
            _ => return Ok(Json(json!({ "items": [] }))), // 空表
        }
    } else {
        (start, end)
    };
    let items: Vec<Value> = kv
        .scan(&lo, &hi)
        .into_iter()
        .map(|(k, v)| json!({ "key": key_lossy(&k), "value": key_lossy(&v) }))
        .collect();
    Ok(Json(json!({ "count": items.len(), "items": items })))
}

fn build_router(state: AppState) -> Router {
    Router::new()
        .route("/kv/{key}", get(get_kv).put(put_kv).delete(delete_kv))
        .route("/kv", get(scan_kv))
        .with_state(state)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let port: u16 = std::env::var("KV_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8090);
    let state = AppState {
        store: Arc::new(Mutex::new(Kv::default())),
    };
    let app = build_router(state);
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", port)).await?;
    println!("ex06 axum KV 服务监听 http://127.0.0.1:{port} （Ctrl-C 退出）");
    axum::serve(listener, app).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::{to_bytes, Body};
    use tower::ServiceExt;

    fn test_state() -> AppState {
        AppState {
            store: Arc::new(Mutex::new(Kv::default())),
        }
    }

    fn json_body(v: Value) -> Body {
        Body::from(v.to_string())
    }

    #[tokio::test]
    async fn kv_store_semantics_unit() {
        let mut kv = Kv::default();
        kv.put(b"a".to_vec(), b"1".to_vec());
        kv.put(b"b".to_vec(), b"2".to_vec());
        assert_eq!(kv.get(b"a"), Some(&b"1"[..]));
        assert!(kv.delete(b"a"));
        assert!(!kv.delete(b"a"), "重复删除返回 false");
        assert_eq!(kv.get(b"a"), None);
    }

    #[tokio::test]
    async fn http_roundtrip_put_get_delete() {
        let app = build_router(test_state());
        // PUT
        let resp = app
            .clone()
            .oneshot(
                axum::http::Request::builder()
                    .method("PUT")
                    .uri("/kv/temperature")
                    .header("content-type", "application/json")
                    .body(json_body(json!({ "value": "36.5" })))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        // GET
        let resp = app
            .clone()
            .oneshot(
                axum::http::Request::builder()
                    .uri("/kv/temperature")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let body = to_bytes(resp.into_body(), 1 << 20).await.unwrap();
        let parsed: Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(parsed["value"], json!("36.5"));
        // DELETE
        let resp = app
            .clone()
            .oneshot(
                axum::http::Request::builder()
                    .method("DELETE")
                    .uri("/kv/temperature")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::NO_CONTENT);
        // 删除后再 GET → 404 且 body 是统一 JSON 错误
        let resp = app
            .oneshot(
                axum::http::Request::builder()
                    .uri("/kv/temperature")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::NOT_FOUND);
        let body = to_bytes(resp.into_body(), 1 << 20).await.unwrap();
        let parsed: Value = serde_json::from_slice(&body).unwrap();
        assert!(parsed["error"].as_str().unwrap().contains("不存在"));
    }

    #[tokio::test]
    async fn http_scan_returns_sorted_range() {
        let app = build_router(test_state());
        for (k, v) in [("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")] {
            app.clone()
                .oneshot(
                    axum::http::Request::builder()
                        .method("PUT")
                        .uri(format!("/kv/{k}"))
                        .header("content-type", "application/json")
                        .body(json_body(json!({ "value": v })))
                        .unwrap(),
                )
                .await
                .unwrap();
        }
        let resp = app
            .oneshot(
                axum::http::Request::builder()
                    .uri("/kv?start=b&end=c")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let body = to_bytes(resp.into_body(), 1 << 20).await.unwrap();
        let parsed: Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(parsed["count"], json!(2));
        assert_eq!(parsed["items"][0]["key"], json!("b"));
        assert_eq!(parsed["items"][1]["key"], json!("c"));
    }
}
