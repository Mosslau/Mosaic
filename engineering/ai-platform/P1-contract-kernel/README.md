# P1 契约内核（AI 平台 · 对应 D1）

> 状态：🚧 进行中
> 所属平台与单元：ai-platform · P1 契约内核（类别：期，对应 D1）
> 对应文档：[AI 平台建设路线](../../ai-platform/AI平台建设路线.md)（§3 核心契约、§5 D1）· [共享底座 README](../../infra/README.md)

## 1. 目标

把 AI 平台 D1 的 5 个契约冻结成**可校验的代码**，并让一个 dummy 服务走完「注册 → 调用 → trace → 账本」：

- 5 个契约：`AssetRef` / `Answer` / `Service` / `Ledger` / `RuntimePort`；
- `POST /v1/register` 注册一个 `Service`（健康状态、endpoint、版本），非法负载返回字段级错误；
- `POST /v1/echo` 提交一个 `Answer`，返回引用摘要（digest）与 trace；
- 账本按 trace 可查，`/metrics` 供 Prometheus 抓取。

**一句话验收**：`./test.sh` 全绿，且注册一次 `Service` 后能在账本里按 trace 查到事件。

## 2. 范围与不做

**做**：

- 契约结构校验（必填、类型、枚举、时间格式、数组元素类型）+ JSON Schema 导出；
- dummy 服务注册 / 回显 / 账本 / 指标；
- 标准库实现，零第三方依赖。

**不做**：

- 真实模型调用、vLLM、embedding（归 D2/D5）；
- 鉴权、租户、审批流（归 D8/D10）；
- 账本落库 / 成本归集（D9 再做，D1 用 JSONL 证明可追溯）；
- `RuntimePort` 的多运行时接入（D8 的核心，当前只冻结 schema）。

## 3. 技术栈

| 层 | 选择 | 说明 |
|---|---|---|
| 语言 | Python 3.9（系统解释器） | 不装第三方包 |
| 契约 | 声明式 spec + 自研校验器 | 与数据平台共用 [`../../infra/kernel/`](../../infra/kernel/) |
| 服务 | `http.server.ThreadingHTTPServer` | dummy，不引 FastAPI |
| 账本 | JSONL（`var/ledger.jsonl`） | `ts / trace_id / event / detail` |
| 指标 | Prometheus 文本格式 | `/metrics` |

## 4. 系统架构

```text
curl / test
    │  POST /v1/register（Service）| /v1/echo（Answer）
    ▼
DummyService（共享 kernel）
    ├── ContractSet.validate(contract, payload)   ← 本单元 contracts.py（5 契约）
    ├── JsonlLedger.append(trace_id, event, detail) → var/ledger.jsonl
    └── GET /health | /metrics | /v1/contracts | /v1/ledger?trace_id=
```

| 契约 | 关键字段 | 用途 |
|---|---|---|
| `AssetRef` | `asset_id`、`kind`、`version`、`uri`、`snapshot_id` | 语料/向量/模型的统一引用 |
| `Answer` | `text`、`citations[]`、`confidence`、`no_evidence` | 答案 + 引用 + 无依据标记 |
| `Service` | `name`、`version`、`endpoint`、`health` | 服务注册与健康 |
| `Ledger` | `ledger_id`、`run_id`、`tokens_*`、`gpu_seconds`、`cost_usd` | 成本与用量账本 |
| `RuntimePort` | `runtime_id`、`capabilities[]`、`approval`、`sandbox` | 运行时发布契约（D8 展开） |

目录：

```text
P1-contract-kernel/
├── src/mosaic_ai_contracts/
│   ├── contracts.py      # 5 契约 spec 与样例
│   └── service.py        # 入口：run("ai-service-registry-dummy", ...)
├── tests/                # 14 项（契约 8 + 服务 6）
├── run.sh                # 起 dummy 服务（默认 18181）
└── test.sh               # 跑测试
```

## 5. 复用的算法实验

AI 平台的检索、生成、规划三条线直接对应仓库里已完成的算法实验（原理复用，代码不直接搬）：

- 注意力机制：[`algorithms/p04-transformer/attention/`](../../../algorithms/p04-transformer/attention/)——理解模型侧「答案从哪来」；
- 最小 RAG 闭环：[`algorithms/p05-generative/mini-rag/`](../../../algorithms/p05-generative/mini-rag/)——D2/D3 检索链路的最小参照；
- MCTS 与规划：[`algorithms/p01-search/mcts/`](../../../algorithms/p01-search/mcts/)——D8 Agent 的任务分解与规划参照。

D1 本身不调用这些算法；它们在 D2/D3/D8 以「实验 → 服务」的方式复现时再回链。

## 6. 验收标准

| 编号 | 通过标准 | 当前状态 | 证据 |
|---|---|---|---|
| `A1-1` | 四契约 schema 冻结 | ✅ 已冻结 5 个（多冻结 `RuntimePort`） | `GET /v1/contracts` 返回 5 个 schema；`test_schema_shape` 通过 |
| `A1-2` | dummy 服务注册 / 发现 | ✅ | 注册 `Service` 返回 201、`registered=true`、trace 头回显 |
| `A1-3` | 一次调用有 trace_id + ledger 事件 | ✅ | `/v1/ledger?trace_id=trace-e2e-ai-001` 返回 `register.accepted` + `echo.accepted` |

**复现命令**：

```bash
cd engineering/ai-platform/P1-contract-kernel
./test.sh                          # 14 项 unittest，实测 5.5s 通过

./run.sh --port 18181 --ledger var/ledger.jsonl &
curl -s -X POST http://127.0.0.1:18181/v1/register \
  -H 'Content-Type: application/json' -H 'X-Trace-Id: trace-e2e-ai-001' \
  -d '{"contract":"Service","kind":"runtime","payload":{"name":"agent-runtime","version":"0.3.0","endpoint":"http://127.0.0.1:18181","health":"healthy"}}'
# → {"trace_id":"trace-e2e-ai-001","contract":"Service","digest":"sha256:3887...","registered":true}
```

实测摘要（2026-11-11）：

```text
Ran 14 tests in 5.532s
OK
```

Prometheus target `host.docker.internal:18181` 状态 `up`（共享底座已抓取）。

## 7. 实施笔记

- **2026-11-11 新建**：5 契约 + dummy 服务 + 14 项测试；与数据平台共用 `mosaic_kernel`，不复制校验器。
- **端口**：默认 `18181`（本机 `18081` 被其他服务占用），与共享底座的 scrape target 对齐。
- **取舍**：`RuntimePort` 在 D1 只冻结字段（`capabilities` / `approval` / `sandbox`），真正的多运行时发布在 D8 用 `agent-service` 或 `agent-core` 兑现。
- **待办**：
  1. `Ledger` 落 PG 并与数据平台账本对齐字段（`run_id` ↔ `trace_id` 映射）；
  2. `Answer.citations` 与数据平台 `EvidenceRef` 做联合 schema（跨平台契约测试）；
  3. D8 启动时把 `RuntimePort` 从 schema 升为可调用的端口（发布 / 事件流 / 审批 / 隔离）；
  4. 与 `agent-service` 的 165 项测试对接，决定它是否作为 D8 的第一个运行时。
