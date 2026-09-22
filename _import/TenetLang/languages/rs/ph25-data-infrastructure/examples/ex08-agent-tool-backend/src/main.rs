//! ph25 ex08：Agent 工具后端（Tool trait / 权限 / 超时 / 审计日志 / 可观测计数）
//!
//! 兑现 roadmap §25「Agent 工具后端要关注权限、超时、审计和可观测性」：把
//! 车辆遥测/KV 数据平台语境的工具（kv.get / kv.put / kv.scan / debug.sleep）
//! 注册进一个带边界的调用器——每次调用先过**权限**（调用方声明的 scope 集合
//! 与工具的 required_scope 比对，拒绝记审计），再按工具**超时预算**包一层
//! `tokio::time::timeout`（超时 504 记审计），成功/失败都写**审计日志**
//! （JSON 行：时间/调用方/工具/决策/耗时；纪律：只记 key 不记 value），最后
//! 累加**可观测计数**（按工具/决策的调用量与累计耗时，`/metrics` 暴露）。
//! 调用链上与 ex06 同款：`Tool` 用 `#[async_trait]` 做 trait object（registry
//! 存 `Vec<Box<dyn Tool>>`），与 roadmap §25 的示例骨架一致。
//!
//! # 验证环境与命令
//! - 验证环境：rustc/cargo 1.92.0（macOS arm64）；依赖需联网拉取（axum 0.8.9、
//!   tokio 1.53、async-trait 0.1.94 等，本机解析版本见 examples/README）
//! - 测试：`cargo test --release`（权限/超时/审计/指标四类单测 + 路由冒烟）
//! - 运行：`cargo run --release`（127.0.0.1:8091），curl 冒烟见 README
//! - 质量：`cargo fmt --check && cargo clippy --all-targets -- -D warnings`
//! - 验证状态：**已验证**（2026-09-04 本机实测）

use async_trait::async_trait;
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::post;
use axum::{Json, Router};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};
use std::time::Instant;

type Kv = BTreeMap<String, String>;

/// 工具调用上下文：谁在调用（权限判定的输入）。
#[derive(Debug, Clone)]
pub struct ToolCtx {
    pub requester: String,
}

/// Agent 工具接口：名称 + 所需权限 scope + 超时预算 + 异步调用。
///
/// `async_trait` 让 trait 能存进 `Vec<Box<dyn Tool>>` 做注册表（trait object 动态分发）。
#[async_trait]
pub trait Tool: Send + Sync {
    fn name(&self) -> &'static str;
    /// 调用它所需的权限 scope（registry 拿它与调用方声明的 scopes 比对）。
    fn required_scope(&self) -> &'static str;
    /// 单次调用的超时预算（路由层用 tokio::time::timeout 强制）。
    fn budget(&self) -> std::time::Duration;
    /// 执行。返回 JSON 结果；错误以字符串返回（调用器统一包装成 4xx/5xx）。
    async fn call(&self, ctx: &ToolCtx, input: Value) -> Result<Value, String>;
}

/// 审计条目（JSON 行）。纪律：**只记 key、不记 value**——value 可能是敏感负载。
#[derive(Debug, serde::Serialize)]
struct AuditLine {
    ts_ms: u128,
    requester: String,
    tool: String,
    decision: String, // allowed / denied / not_found / timeout / internal_error
    duration_ms: f64,
    note: String,
}

/// 可观测计数：按 (工具 × 决策) 的调用量与累计耗时。
#[derive(Debug, Default)]
struct Metrics {
    total_calls: u64,
    by_tool: BTreeMap<String, u64>,
    by_decision: BTreeMap<String, u64>,
    sum_duration_ms: f64,
}

#[derive(Clone)]
struct ToolRegistry {
    tools: Arc<Vec<Box<dyn Tool>>>,
    /// 调用方 → 被授权的 scope 集合（最小权限的落点：只给工具够用的 scope）。
    scopes: Arc<BTreeMap<String, Vec<String>>>,
    audit: Arc<Mutex<Vec<AuditLine>>>,
    metrics: Arc<Mutex<Metrics>>,
}

impl ToolRegistry {
    fn new(tools: Vec<Box<dyn Tool>>, scopes: BTreeMap<String, Vec<String>>) -> ToolRegistry {
        ToolRegistry {
            tools: Arc::new(tools),
            scopes: Arc::new(scopes),
            audit: Arc::new(Mutex::new(Vec::new())),
            metrics: Arc::new(Mutex::new(Metrics::default())),
        }
    }

    fn tool(&self, name: &str) -> Option<&dyn Tool> {
        self.tools
            .iter()
            .find(|t| t.name() == name)
            .map(Box::as_ref)
    }

    fn has_scope(&self, requester: &str, scope: &str) -> bool {
        self.scopes
            .get(requester)
            .is_some_and(|scopes| scopes.iter().any(|s| s == scope))
    }

    fn audit_line(&self, line: AuditLine) {
        self.audit
            .lock()
            .expect("audit 锁中毒仅可能由 panic 引起（本示例无）")
            .push(line);
    }

    fn record_metric(&self, tool: &str, decision: &str, duration_ms: f64) {
        let mut m = self.metrics.lock().expect("metrics 锁中毒，同上");
        m.total_calls += 1;
        *m.by_tool.entry(tool.to_string()).or_default() += 1;
        *m.by_decision.entry(decision.to_string()).or_default() += 1;
        m.sum_duration_ms += duration_ms;
    }

    /// 带边界的工具调用：权限 → 超时 → 执行 → 审计 + 指标。
    async fn call(
        &self,
        requester: &str,
        tool_name: &str,
        input: Value,
    ) -> Result<Value, ToolFail> {
        let started = Instant::now();
        let ctx = ToolCtx {
            requester: requester.to_string(),
        };
        let Some(tool) = self.tool(tool_name) else {
            let fail = ToolFail::not_found(format!("工具 '{tool_name}' 不存在"));
            self.finish(&ctx, tool_name, "not_found", started, &fail.message);
            return Err(fail);
        };
        if !self.has_scope(requester, tool.required_scope()) {
            let fail = ToolFail::forbidden(format!(
                "'{requester}' 无权调用 {tool_name}（需要 scope '{}'）",
                tool.required_scope()
            ));
            self.finish(&ctx, tool_name, "denied", started, &fail.message);
            return Err(fail);
        }
        match tokio::time::timeout(tool.budget(), tool.call(&ctx, input)).await {
            Err(_elapsed) => {
                let fail =
                    ToolFail::timeout(format!("工具 {tool_name} 超过超时预算 {:?}", tool.budget()));
                self.finish(&ctx, tool_name, "timeout", started, &fail.message);
                Err(fail)
            }
            Ok(Err(e)) => {
                let fail = ToolFail::internal(e);
                self.finish(&ctx, tool_name, "internal_error", started, &fail.message);
                Err(fail)
            }
            Ok(Ok(v)) => {
                self.finish(&ctx, tool_name, "allowed", started, "ok");
                Ok(v)
            }
        }
    }

    fn finish(&self, ctx: &ToolCtx, tool_name: &str, decision: &str, started: Instant, note: &str) {
        let duration_ms = started.elapsed().as_secs_f64() * 1e3;
        self.audit_line(AuditLine {
            ts_ms: now_ms(),
            requester: ctx.requester.clone(),
            tool: tool_name.to_string(),
            decision: decision.to_string(),
            duration_ms,
            note: note.to_string(),
        });
        self.record_metric(tool_name, decision, duration_ms);
    }

    fn audit_json(&self) -> Vec<Value> {
        self.audit
            .lock()
            .expect("audit 锁中毒")
            .iter()
            .map(|a| serde_json::to_value(a).expect("AuditLine 可序列化"))
            .collect()
    }

    fn metrics_json(&self) -> Value {
        let m = self.metrics.lock().expect("metrics 锁中毒");
        json!({
            "total_calls": m.total_calls,
            "by_tool": m.by_tool,
            "by_decision": m.by_decision,
            "sum_duration_ms": (m.sum_duration_ms * 100.0).round() / 100.0,
        })
    }
}

fn now_ms() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("系统时间早于 1970")
        .as_millis()
}

/// 统一的调用失败：HTTP 状态 + 机器码 + 人类可读消息。
#[derive(Debug)]
struct ToolFail {
    http: StatusCode,
    code: &'static str,
    message: String,
}

impl ToolFail {
    fn not_found(message: String) -> ToolFail {
        ToolFail {
            http: StatusCode::NOT_FOUND,
            code: "tool_not_found",
            message,
        }
    }
    fn forbidden(message: String) -> ToolFail {
        ToolFail {
            http: StatusCode::FORBIDDEN,
            code: "permission_denied",
            message,
        }
    }
    fn timeout(message: String) -> ToolFail {
        ToolFail {
            http: StatusCode::GATEWAY_TIMEOUT,
            code: "tool_timeout",
            message,
        }
    }
    fn internal(message: String) -> ToolFail {
        ToolFail {
            http: StatusCode::INTERNAL_SERVER_ERROR,
            code: "tool_internal_error",
            message,
        }
    }
}

impl IntoResponse for ToolFail {
    fn into_response(self) -> Response {
        let body = Json(json!({ "error": { "code": self.code, "message": self.message } }));
        (self.http, body).into_response()
    }
}

// —— 具体工具：遥测/KV 语境 ——

struct KvGet {
    store: Arc<Mutex<Kv>>,
}

#[async_trait]
impl Tool for KvGet {
    fn name(&self) -> &'static str {
        "kv.get"
    }
    fn required_scope(&self) -> &'static str {
        "kv:read"
    }
    fn budget(&self) -> std::time::Duration {
        std::time::Duration::from_millis(200)
    }
    async fn call(&self, _ctx: &ToolCtx, input: Value) -> Result<Value, String> {
        let key = input
            .get("key")
            .and_then(Value::as_str)
            .ok_or_else(|| "缺少字符串字段 key".to_string())?;
        let store = self.store.lock().map_err(|_| "kv 锁中毒".to_string())?;
        match store.get(key) {
            Some(v) => Ok(json!({ "key": key, "value": v })),
            None => Ok(json!({ "key": key, "value": null })), // Agent 语义：不存在也是合法输出
        }
    }
}

struct KvPut {
    store: Arc<Mutex<Kv>>,
}

#[async_trait]
impl Tool for KvPut {
    fn name(&self) -> &'static str {
        "kv.put"
    }
    fn required_scope(&self) -> &'static str {
        "kv:write"
    }
    fn budget(&self) -> std::time::Duration {
        std::time::Duration::from_millis(200)
    }
    async fn call(&self, _ctx: &ToolCtx, input: Value) -> Result<Value, String> {
        let key = input
            .get("key")
            .and_then(Value::as_str)
            .ok_or_else(|| "缺少字符串字段 key".to_string())?;
        let value = input
            .get("value")
            .and_then(Value::as_str)
            .ok_or_else(|| "缺少字符串字段 value".to_string())?;
        self.store
            .lock()
            .map_err(|_| "kv 锁中毒".to_string())?
            .insert(key.to_string(), value.to_string());
        Ok(json!({ "key": key, "written": true }))
    }
}

struct KvScan {
    store: Arc<Mutex<Kv>>,
}

#[async_trait]
impl Tool for KvScan {
    fn name(&self) -> &'static str {
        "kv.scan"
    }
    fn required_scope(&self) -> &'static str {
        "kv:read"
    }
    fn budget(&self) -> std::time::Duration {
        std::time::Duration::from_millis(300)
    }
    async fn call(&self, _ctx: &ToolCtx, input: Value) -> Result<Value, String> {
        let start = input
            .get("start")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let end = input
            .get("end")
            .and_then(Value::as_str)
            .unwrap_or("\u{10FFFF}")
            .to_string();
        let store = self.store.lock().map_err(|_| "kv 锁中毒".to_string())?;
        let items: Vec<Value> = store
            .range(start..=end)
            .map(|(k, v)| json!({ "key": k, "value": v }))
            .collect();
        Ok(json!({ "count": items.len(), "items": items }))
    }
}

/// 慢工具：让路由层的超时预算可见（默认预算 30ms，工具故意睡 100ms）。
struct DebugSleep;

#[async_trait]
impl Tool for DebugSleep {
    fn name(&self) -> &'static str {
        "debug.sleep"
    }
    fn required_scope(&self) -> &'static str {
        "debug:*"
    }
    fn budget(&self) -> std::time::Duration {
        std::time::Duration::from_millis(30)
    }
    async fn call(&self, _ctx: &ToolCtx, _input: Value) -> Result<Value, String> {
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        Ok(json!({ "slept": 100 }))
    }
}

// —— HTTP 面 ——

#[derive(Clone)]
struct AppState {
    registry: Arc<ToolRegistry>,
}

fn build_router(registry: Arc<ToolRegistry>) -> Router {
    Router::new()
        .route("/tools/call", post(handle_call))
        .route("/metrics", axum::routing::get(handle_metrics))
        .route("/audit", axum::routing::get(handle_audit))
        .with_state(AppState { registry })
}

async fn handle_call(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(body): Json<Value>,
) -> Response {
    let requester = headers
        .get("x-client-id")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("anonymous")
        .to_string();
    let tool_name = body
        .get("tool")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    let input = body.get("input").cloned().unwrap_or(json!({}));
    match state.registry.call(&requester, &tool_name, input).await {
        Ok(output) => (StatusCode::OK, Json(json!({ "output": output }))).into_response(),
        Err(fail) => fail.into_response(),
    }
}

async fn handle_metrics(State(state): State<AppState>) -> Json<Value> {
    Json(state.registry.metrics_json())
}

async fn handle_audit(State(state): State<AppState>) -> Json<Value> {
    Json(json!({ "entries": state.registry.audit_json() }))
}

fn demo_registry() -> (Arc<ToolRegistry>, Arc<Mutex<Kv>>) {
    let store: Arc<Mutex<Kv>> = Arc::new(Mutex::new(Kv::new()));
    let kv_store = Arc::clone(&store);
    let tools: Vec<Box<dyn Tool>> = vec![
        Box::new(KvGet {
            store: Arc::clone(&kv_store),
        }),
        Box::new(KvPut {
            store: Arc::clone(&kv_store),
        }),
        Box::new(KvScan {
            store: Arc::clone(&kv_store),
        }),
        Box::new(DebugSleep),
    ];
    let scopes = BTreeMap::from([
        ("reader".to_string(), vec!["kv:read".to_string()]),
        (
            "writer".to_string(),
            vec!["kv:read".to_string(), "kv:write".to_string()],
        ),
        (
            "admin".to_string(),
            vec![
                "kv:read".to_string(),
                "kv:write".to_string(),
                "debug:*".to_string(),
            ],
        ),
    ]);
    (Arc::new(ToolRegistry::new(tools, scopes)), store)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let port: u16 = std::env::var("TOOL_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8091);
    let (registry, _store) = demo_registry();
    let app = build_router(registry);
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", port)).await?;
    println!(
        "ex08 Agent 工具服务监听 http://127.0.0.1:{port}（POST /tools/call，GET /metrics /audit）"
    );
    axum::serve(listener, app).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::{to_bytes, Body};

    async fn call_json(reg: &ToolRegistry, requester: &str, body: Value) -> (StatusCode, Value) {
        match reg
            .call(
                requester,
                body["tool"].as_str().unwrap_or_default(),
                body["input"].clone(),
            )
            .await
        {
            Ok(v) => (StatusCode::OK, json!({ "output": v })),
            Err(f) => (
                f.http,
                json!({ "error": { "code": f.code, "message": f.message } }),
            ),
        }
    }

    #[tokio::test]
    async fn permission_denied_then_granted() {
        let (reg, store) = demo_registry();
        // reader 无权写
        let (status, body) = call_json(
            &reg,
            "reader",
            json!({ "tool": "kv.put", "input": { "key": "a", "value": "1" } }),
        )
        .await;
        assert_eq!(status, StatusCode::FORBIDDEN);
        assert_eq!(body["error"]["code"], "permission_denied");
        assert!(store.lock().unwrap().is_empty());
        // writer 有权写
        let (status, _) = call_json(
            &reg,
            "writer",
            json!({ "tool": "kv.put", "input": { "key": "a", "value": "1" } }),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            store.lock().unwrap().get("a").map(String::as_str),
            Some("1")
        );
        // 审计里有 denied + allowed 两条
        let audit = reg.audit_json();
        let decisions: Vec<&str> = audit
            .iter()
            .map(|a| a["decision"].as_str().unwrap())
            .collect();
        assert!(decisions.contains(&"denied"));
        assert!(decisions.contains(&"allowed"));
        // 审计只记 key 不记 value：note 里不应出现 "1"
        assert!(audit.iter().all(|a| a["note"].as_str().unwrap() != "1"));
    }

    #[tokio::test]
    async fn timeout_is_enforced_and_audited() {
        let (reg, _store) = demo_registry();
        let (status, body) =
            call_json(&reg, "admin", json!({ "tool": "debug.sleep", "input": {} })).await;
        assert_eq!(status, StatusCode::GATEWAY_TIMEOUT);
        assert_eq!(body["error"]["code"], "tool_timeout");
        let audit = reg.audit_json();
        assert!(audit.iter().any(|a| a["decision"] == "timeout"));
    }

    #[tokio::test]
    async fn unknown_tool_and_metrics_counters() {
        let (reg, _store) = demo_registry();
        let (status, _) = call_json(&reg, "admin", json!({ "tool": "nope", "input": {} })).await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        let m = reg.metrics_json();
        assert_eq!(m["total_calls"], 1);
        assert_eq!(m["by_decision"]["not_found"], 1);
    }

    #[tokio::test]
    async fn http_route_smoke() {
        let (registry, _store) = demo_registry();
        let app = build_router(registry);
        // 用 tower ServiceExt 直连路由（等价 HTTP）
        let req = axum::http::Request::builder()
            .method("POST")
            .uri("/tools/call")
            .header("content-type", "application/json")
            .header("x-client-id", "writer")
            .body(Body::from(
                json!({ "tool": "kv.put", "input": { "key": "t", "value": "36.5" } }).to_string(),
            ))
            .unwrap();
        let resp = tower::ServiceExt::oneshot(app, req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let bytes = to_bytes(resp.into_body(), 1 << 20).await.unwrap();
        let parsed: Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(parsed["output"]["written"], true);
    }
}
