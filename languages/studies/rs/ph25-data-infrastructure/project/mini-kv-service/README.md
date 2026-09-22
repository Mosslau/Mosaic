# ph25 阶段项目：mini-kv-service（收官三合一）

> 对应 roadmap 第 25 节「推荐项目」与附录「阶段性项目验收标准」：Rust 路线收官工程。
> 落地为 **Mini LSM-KV 持久化引擎 + Axum HTTP + Agent 工具 API** 的三合一服务——
> 一台可跑、可崩、可恢复的最小 KV 服务。它把本阶段 examples/ex01~ex08 演示的组件
> 收进一个「服务进程」：WAL（ex01）当持久化底座、有序内存表提供 range scan（ex02
> 语义）、Axum 暴露 CRUD 与扫描（ex06 形态）、工具调用带权限/审计/计数（ex08 形态）。

## 需求

三合一服务回答三句话：

1. **写得安全**：任何 `put/delete` 先落 WAL（fsync 才确认）再改内存表——崩溃/重启后 WAL 重放恢复；
2. **读得有序**：key 在有序内存表里，`get` 点查、`scan` 闭区间返回——range scan 是 HTTP 一等公民；
3. **调得可信**：Agent 工具 API（`/tools/call`）按 `x-client-id` 声明权限 scope，逐次调用写审计、按决策计数，`/metrics` 暴露。

边界声明（诚实标注）：本工程不实现多级 SSTable 与后台 compaction——它们是 examples/ex02~ex03 与 exercises/sol-02~sol-03 演示过的组件；这里把它们「留到引擎接入点」，把精力放在「可测试可部署的持久化服务」上。pyo3 模块可选（见 ex07），本工程不内嵌。

## 目录与功能清单

```text
mini-kv-service/
├── Cargo.toml / Cargo.lock   # axum 0.8.9 / tokio 1.53.1 / serde 1.0.229（实测版本）
├── deny.toml                 # 复制自 ph24 relpipe/deny.toml（注明来源），schema 经 cargo-deny 校验
├── release-check.sh          # 形态复制自 ph24 relpipe/release-check.sh（本地 9 步流水线）
├── CHANGELOG.md              # [Unreleased] + [0.1.0]
├── README.md                 # 本文件
├── scripts/smoke.sh          # HTTP 冒烟：CRUD / scan / 工具权限 / 重启恢复
└── src/
    ├── lib.rs                # 库入口：engine + api
    ├── engine.rs             # WAL + MemTable（崩溃恢复、残尾修复、range scan）
    ├── api.rs                # Router：/kv/*、/kv、/tools/call、/metrics、/audit、/healthz
    └── main.rs               # 服务入口（KV_PORT / KV_DATA 环境变量）
```

功能清单：

- [x] `put/delete/get`：WAL append + fsync 后才确认（ex01/sol-01 纪律）
- [x] 崩溃恢复：重启同一 `KV_DATA` 目录，WAL 重放还原状态；残尾自动截断
- [x] range scan：`GET /kv?start=&end=`（闭区间、空区间安全返回空）
- [x] HTTP CRUD：`GET/PUT/DELETE /kv/{key}`、`/healthz`
- [x] Agent 工具：`POST /tools/call`（`x-client-id` → scope 校验 → 审计 + 决策计数）
- [x] `/audit` 审计查询、`/metrics` 计数端点
- [x] deny.toml / release-check.sh：ph24 供应链门禁与流水线直接复用（来源注明）

## 验证环境

rustc/cargo **1.92.0**（macOS arm64）；依赖经网络解析（Cargo.lock 已提交）：axum **0.8.9**、tokio **1.53.1**、serde **1.0.229**、serde_json **1.0.151**；cargo-audit **0.22.2**、cargo-deny **0.20.2**（release-check.sh 用到）。构建产物统一落 `CARGO_TARGET_DIR`（默认 `/tmp/ph25-project-target`），仓库零二进制残留。

## 验收标准

在 `project/mini-kv-service/` 目录内执行：

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph25-project-target
cargo fmt --check                       # 格式
cargo clippy --all-targets -- -D warnings   # lint：零警告
cargo test --release                    # 5 测试全绿（引擎恢复 ×3 + HTTP CRUD/scan + 工具权限/审计）
./scripts/smoke.sh                      # HTTP 冒烟：CRUD/scan/工具权限/重启恢复
./release-check.sh                      # ph24 形态 9 步流水线（fmt/clippy/test/audit/deny/package）
```

**四关验收对应 roadmap**：

| 关卡 | 验收点 | 位置 |
|------|--------|------|
| WAL 恢复 | 同一 `KV_DATA` 两次启动：第二次 GET 到第一次 PUT 的值 | `engine.rs` + smoke「重启恢复」段 |
| range scan | `GET /kv?start=&end=` 返回闭区间有序条目 | `engine.scan` + `api.scan_kv` + smoke |
| HTTP CRUD | PUT/GET/DELETE 返回 200/404/204 与统一 JSON 错误 | `api.rs` tests + smoke |
| 工具调用 | writer 可 put、reader 越权 403、`/audit` 有记录、`/metrics` 有计数 | `api.rs` tests + smoke |

**本机实测（2026-09-04）**：

- `cargo test --release`：5 passed（engine::tests ×3 + api::tests ×2）
- `./scripts/smoke.sh` 输出要点：
  - PUT ×3 → GET 命中 `{"key":"temperature","value":"36.5"}` → DELETE 204
  - scan `?start=temperature&end=voltage` → `count:2`（有序）
  - **重启同一数据目录后 GET `/kv/voltage` 仍返回 `12.8`**（WAL 重放），被删的 pressure 404
  - 工具：writer `kv.put` accepted；reader 越权返回 `[403] {'error':"'reader' 无权调用 kv.put…"}`
  - `/metrics`：`{"decision:allowed":1,"decision:denied":1,...}`；`/audit` 两条 JSON 审计行
- `./release-check.sh` 9 步实测：fmt OK → clippy 0 warnings → test 5 passed → audit 无已知漏洞（RustSec db 1239 条）→ deny licenses/bans 全绿（advisories 因 db fetch 网络问题降级警告，由 audit step 硬性覆盖）→ `cargo deny list` 输出 8 个许可 ×N 包 → `cargo package` 演练 OK（release-check 日志 /tmp/ph25-relcheck.log）。**真实 `cargo publish` 未在本环境验证**。

## 扩展方向

- **持久化性能档**：把每次写 fsync 换成攒批 group commit（ex01 组提交语义），吞吐与可靠性交给水位参数
- **多级 SSTable + 后台 compaction**：把 engine 的内存表接到 examples/ex02 的 SSTable writer/reader、exercises/sol-03 的归并语义，做成完整 Mini LSM（roadmap 尾部的演进方向）
- **服务超时**：工具 API 接 ex08 的每工具超时预算（当前均为进程内快速操作，无慢路径）
- **pyo3 加速**：把 parse/distance 热路径做成 Python 模块（examples/ex07 的工程形态）给 RAG 侧用
- **观测增强**：把 println 审计换成 tracing + 结构化日志、指标进 Prometheus 文本格式
