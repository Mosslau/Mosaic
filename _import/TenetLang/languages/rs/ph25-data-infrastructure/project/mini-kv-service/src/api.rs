//! HTTP / Agent 工具 API 面：把 engine::Engine 暴露成 REST 与工具调用两种形态。
//!
//! - REST：GET/PUT/DELETE `/kv/{key}`、GET `/kv?start=&end=`（range scan）、`/healthz`；
//! - Agent 工具：POST `/tools/call`（`x-client-id` 声明调用方）→ 权限 scope 校验 →
//!   执行 → 审计 JSON 行 + 决策/吞吐计数（`/metrics` 暴露）——工具边界（权限/
//!   审计/可观测）来自 ex08 的形态；耗时敏感工具的「超时预算」是 ex08 的专门主题，
//!   本项目工具均为进程内快速操作，不引入异步超时（README 说明分工）。

use crate::engine::Engine;
use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex, MutexGuard};

/// 进程级状态：引擎（写路径串行化）+ 审计日志 + 调用计数。
#[derive(Clone)]
pub struct AppState {
    engine: Arc<Mutex<Engine>>,
    audit: Arc<Mutex<Vec<Value>>>,
    counts: Arc<Mutex<BTreeMap<String, u64>>>,
    /// 调用方 → 被授权 scope（最小权限）。
    scopes: Arc<BTreeMap<String, Vec<String>>>,
}

impl AppState {
    pub fn open(dir: PathBuf) -> Result<AppState, crate::engine::EngError> {
        let engine = Engine::open(&dir)?;
        let scopes = BTreeMap::from([
            ("reader".to_string(), vec!["kv:read".to_string()]),
            (
                "writer".to_string(),
                vec!["kv:read".to_string(), "kv:write".to_string()],
            ),
        ]);
        Ok(AppState {
            engine: Arc::new(Mutex::new(engine)),
            audit: Arc::new(Mutex::new(Vec::new())),
            counts: Arc::new(Mutex::new(BTreeMap::new())),
            scopes: Arc::new(scopes),
        })
    }

    fn lock_engine(&self) -> Result<MutexGuard<'_, Engine>, ApiError> {
        self.engine
            .lock()
            .map_err(|_| ApiError::internal("engine 锁中毒：写路径 panic"))
    }

    fn lock_counts(&self) -> Result<MutexGuard<'_, BTreeMap<String, u64>>, ApiError> {
        self.counts
            .lock()
            .map_err(|_| ApiError::internal("counts 锁中毒"))
    }

    fn inc(&self, key: &str) -> Result<(), ApiError> {
        *self.lock_counts()?.entry(key.to_string()).or_default() += 1;
        Ok(())
    }

    fn audit_line(&self, requester: &str, tool: &str, decision: &str, note: &str) {
        if let Ok(mut audit) = self.audit.lock() {
            audit.push(json!({
                "ts_ms": now_ms(),
                "requester": requester,
                "tool": tool,
                "decision": decision,
                "note": note,
            }));
        }
    }

    /// 工具调用入口：权限 → 执行 → 审计 + 计数。
    fn call_tool(&self, requester: &str, tool: &str, input: Value) -> Result<Value, ApiError> {
        let decision = match tool {
            "kv.get" => self.tool_kv_get(requester, input)?,
            "kv.put" => self.tool_kv_put(requester, input)?,
            "kv.scan" => self.tool_kv_scan(requester, input)?,
            other => {
                let note = format!("工具 '{other}' 不存在");
                self.inc("decision:not_found")?;
                self.audit_line(requester, other, "not_found", &note);
                return Err(ApiError::not_found(&note));
            }
        };
        let _ = decision;
        Ok(Value::Null)
    }

    fn require_scope(&self, requester: &str, scope: &str, tool: &str) -> Result<(), ApiError> {
        let ok = self
            .scopes
            .get(requester)
            .is_some_and(|scopes| scopes.iter().any(|s| s == scope));
        if !ok {
            let note = format!("'{requester}' 无权调用 {tool}（需要 scope '{scope}'）");
            self.inc("decision:denied")?;
            self.audit_line(requester, tool, "denied", &note);
            return Err(ApiError::forbidden(&note));
        }
        Ok(())
    }

    fn finish_tool(&self, requester: &str, tool: &str) -> Result<(), ApiError> {
        self.inc("decision:allowed")?;
        self.audit_line(requester, tool, "allowed", "ok");
        Ok(())
    }

    fn tool_kv_get(&self, requester: &str, input: Value) -> Result<(), ApiError> {
        self.require_scope(requester, "kv:read", "kv.get")?;
        let key = str_field(&input, "key")?;
        let engine = self.lock_engine()?;
        let value = engine.get(key.as_bytes()).map(key_lossy);
        drop(engine);
        self.finish_tool(requester, "kv.get")?;
        if let Some(v) = value {
            println!("[tool kv.get] {requester}: {key} = {v}");
        } else {
            println!("[tool kv.get] {requester}: {key} = <miss>");
        }
        Ok(())
    }

    fn tool_kv_put(&self, requester: &str, input: Value) -> Result<(), ApiError> {
        self.require_scope(requester, "kv:write", "kv.put")?;
        let key = str_field(&input, "key")?;
        let value = str_field(&input, "value")?;
        let mut engine = self.lock_engine()?;
        engine
            .put(key.as_bytes(), value.as_bytes())
            .map_err(ApiError::engine)?;
        drop(engine);
        self.finish_tool(requester, "kv.put")?;
        println!("[tool kv.put] {requester}: {key} = {value}");
        Ok(())
    }

    fn tool_kv_scan(&self, requester: &str, input: Value) -> Result<(), ApiError> {
        self.require_scope(requester, "kv:read", "kv.scan")?;
        let start = input
            .get("start")
            .and_then(Value::as_str)
            .unwrap_or("")
            .as_bytes()
            .to_vec();
        let end = input
            .get("end")
            .and_then(Value::as_str)
            .unwrap_or("\u{10FFFF}")
            .as_bytes()
            .to_vec();
        let engine = self.lock_engine()?;
        let rows = engine.scan(&start, &end);
        drop(engine);
        self.finish_tool(requester, "kv.scan")?;
        println!("[tool kv.scan] {requester}: {} 条", rows.len());
        Ok(())
    }
}

fn now_ms() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("系统时间早于 1970")
        .as_millis()
}

fn key_lossy(k: &[u8]) -> String {
    String::from_utf8_lossy(k).into_owned()
}

fn str_field(input: &Value, name: &str) -> Result<String, ApiError> {
    input
        .get(name)
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| ApiError::internal(format!("input 缺少字符串字段 '{name}'")))
}

#[derive(Debug)]
enum ApiError {
    NotFound(String),
    Forbidden(String),
    Internal(String),
}

impl ApiError {
    fn not_found(msg: &str) -> ApiError {
        ApiError::NotFound(msg.to_string())
    }
    fn forbidden(msg: &str) -> ApiError {
        ApiError::Forbidden(msg.to_string())
    }
    fn internal(msg: impl Into<String>) -> ApiError {
        ApiError::Internal(msg.into())
    }
    fn engine(e: impl std::fmt::Display) -> ApiError {
        ApiError::Internal(format!("引擎错误：{e}"))
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, msg) = match self {
            ApiError::NotFound(m) => (StatusCode::NOT_FOUND, m),
            ApiError::Forbidden(m) => (StatusCode::FORBIDDEN, m),
            ApiError::Internal(m) => (StatusCode::INTERNAL_SERVER_ERROR, m),
        };
        (status, Json(json!({ "error": msg }))).into_response()
    }
}

// ================= REST handlers =================

async fn get_kv(
    State(state): State<AppState>,
    Path(key): Path<String>,
) -> Result<Json<Value>, ApiError> {
    state.inc("http:get")?;
    let engine = state.lock_engine()?;
    match engine.get(key.as_bytes()) {
        Some(v) => Ok(Json(json!({ "key": key, "value": key_lossy(v) }))),
        None => Err(ApiError::not_found(&format!("key '{key}' 不存在"))),
    }
}

async fn put_kv(
    State(state): State<AppState>,
    Path(key): Path<String>,
    Json(body): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    state.inc("http:put")?;
    let value = body
        .get("value")
        .and_then(Value::as_str)
        .ok_or_else(|| ApiError::internal("body 需要 JSON 字符串字段 \"value\""))?
        .to_string();
    let mut engine = state.lock_engine()?;
    engine
        .put(key.as_bytes(), value.as_bytes())
        .map_err(ApiError::engine)?;
    Ok(Json(json!({ "key": key, "value": value, "written": true })))
}

async fn delete_kv(
    State(state): State<AppState>,
    Path(key): Path<String>,
) -> Result<StatusCode, ApiError> {
    state.inc("http:delete")?;
    let mut engine = state.lock_engine()?;
    if engine.get(key.as_bytes()).is_some() {
        engine.delete(key.as_bytes()).map_err(ApiError::engine)?;
        Ok(StatusCode::NO_CONTENT)
    } else {
        Err(ApiError::not_found(&format!("key '{key}' 不存在")))
    }
}

#[derive(Debug, Deserialize)]
struct ScanQuery {
    start: Option<String>,
    end: Option<String>,
}

async fn scan_kv(
    State(state): State<AppState>,
    Query(q): Query<ScanQuery>,
) -> Result<Json<Value>, ApiError> {
    state.inc("http:scan")?;
    let start = q.start.unwrap_or_default().into_bytes();
    let end = q
        .end
        .unwrap_or_else(|| "\u{10FFFF}".to_string())
        .into_bytes();
    let engine = state.lock_engine()?;
    let items: Vec<Value> = engine
        .scan(&start, &end)
        .into_iter()
        .map(|(k, v)| json!({ "key": key_lossy(&k), "value": key_lossy(&v) }))
        .collect();
    Ok(Json(json!({ "count": items.len(), "items": items })))
}

async fn healthz(State(state): State<AppState>) -> Json<Value> {
    let engine = state.lock_engine();
    match engine {
        Ok(engine) => Json(json!({
            "status": "ok",
            "keys": engine.len(),
            "ops": engine.ops,
            "torn_recovered": engine.torn_recovered,
        })),
        Err(_) => Json(json!({ "status": "degraded" })),
    }
}

// ================= Agent 工具 =================

#[derive(Debug, Deserialize)]
struct ToolCallBody {
    tool: String,
    #[serde(default)]
    input: Value,
}

async fn call_tool(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(body): Json<ToolCallBody>,
) -> Result<Json<Value>, ApiError> {
    let requester = headers
        .get("x-client-id")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("anonymous")
        .to_string();
    match state.call_tool(&requester, &body.tool, body.input) {
        Ok(_) => Ok(Json(json!({ "accepted": true, "tool": body.tool }))),
        Err(e) => Err(e),
    }
}

async fn metrics(State(state): State<AppState>) -> Json<Value> {
    let counts = state.counts.lock().map(|c| c.clone()).unwrap_or_default();
    Json(json!({ "counts": counts }))
}

async fn audit(State(state): State<AppState>) -> Json<Value> {
    let entries = state.audit.lock().map(|a| a.clone()).unwrap_or_default();
    Json(json!({ "entries": entries }))
}

/// 组装路由。
pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/healthz", get(healthz))
        .route("/kv/{key}", get(get_kv).put(put_kv).delete(delete_kv))
        .route("/kv", get(scan_kv))
        .route("/tools/call", axum::routing::post(call_tool))
        .route("/metrics", get(metrics))
        .route("/audit", get(audit))
        .with_state(state)
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::{to_bytes, Body};
    use tower::ServiceExt;

    fn tmpdir(name: &str) -> PathBuf {
        let d =
            std::env::temp_dir().join(format!("ph25-project-api-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        d
    }

    fn json_body(v: Value) -> Body {
        Body::from(v.to_string())
    }

    async fn call(
        app: &Router,
        method: &str,
        uri: &str,
        body: Option<Value>,
        client: Option<&str>,
    ) -> (StatusCode, Value) {
        let mut req = axum::http::Request::builder().method(method).uri(uri);
        if let Some(c) = client {
            req = req.header("x-client-id", c);
        }
        let b = body.map(json_body).unwrap_or_else(|| Body::empty());
        let req = req
            .header("content-type", "application/json")
            .body(b)
            .unwrap();
        let resp = app.clone().oneshot(req).await.unwrap();
        let status = resp.status();
        let bytes = to_bytes(resp.into_body(), 1 << 20).await.unwrap();
        let parsed = if bytes.is_empty() {
            Value::Null
        } else {
            serde_json::from_slice(&bytes).unwrap()
        };
        (status, parsed)
    }

    #[tokio::test]
    async fn http_crud_and_scan() {
        let app = router(AppState::open(tmpdir("http")).unwrap());
        // PUT x2 + GET + DELETE
        let (s, _) = call(
            &app,
            "PUT",
            "/kv/voltage",
            Some(json!({"value": "12.8"})),
            None,
        )
        .await;
        assert_eq!(s, StatusCode::OK);
        let (s, body) = call(&app, "GET", "/kv/voltage", None, None).await;
        assert_eq!(s, StatusCode::OK);
        assert_eq!(body["value"], json!("12.8"));
        let (s, _) = call(
            &app,
            "PUT",
            "/kv/temperature",
            Some(json!({"value": "36.5"})),
            None,
        )
        .await;
        assert_eq!(s, StatusCode::OK);
        let (s, body) = call(&app, "GET", "/kv?start=temperature&end=voltage", None, None).await;
        assert_eq!(s, StatusCode::OK);
        assert_eq!(body["count"], json!(2));
        let (s, _) = call(&app, "DELETE", "/kv/voltage", None, None).await;
        assert_eq!(s, StatusCode::NO_CONTENT);
        let (s, _) = call(&app, "GET", "/kv/voltage", None, None).await;
        assert_eq!(s, StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn tool_permission_and_audit() {
        let app = router(AppState::open(tmpdir("tool")).unwrap());
        // writer 有权 put
        let (s, _) = call(
            &app,
            "POST",
            "/tools/call",
            Some(json!({"tool": "kv.put", "input": {"key": "x", "value": "1"}})),
            Some("writer"),
        )
        .await;
        assert_eq!(s, StatusCode::OK);
        // reader 无权 put
        let (s, body) = call(
            &app,
            "POST",
            "/tools/call",
            Some(json!({"tool": "kv.put", "input": {"key": "x", "value": "1"}})),
            Some("reader"),
        )
        .await;
        assert_eq!(s, StatusCode::FORBIDDEN);
        assert_eq!(body["error"].as_str().unwrap().contains("无权"), true);
        // 审计有 allowed/denied，且 GET /audit 能读出
        let (s, body) = call(&app, "GET", "/audit", None, None).await;
        assert_eq!(s, StatusCode::OK);
        let decisions: Vec<&str> = body["entries"]
            .as_array()
            .unwrap()
            .iter()
            .map(|e| e["decision"].as_str().unwrap())
            .collect();
        assert!(decisions.contains(&"allowed"));
        assert!(decisions.contains(&"denied"));
    }
}
