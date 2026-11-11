# P1 契约内核（数据平台 · 对应 D1）

> 状态：🚧 进行中
> 所属平台与单元：data-platform · P1 契约内核（类别：期，对应 D1）
> 对应文档：[通用数据平台建设路线](../../data-platform/通用数据平台建设路线.md)（§2.5 核心契约、§5 D1）· [共享底座 README](../../infra/README.md)

## 1. 目标

把数据平台 D1 的 7 个契约冻结成**可校验的代码**，并让一个 dummy 源走完「注册 → 调用 → trace → 账本」：

- 7 个契约：`Envelope` / `TableRef` / `MetricDef` / `MQL` / `LineageEvent` / `Policy` / `QueryRequest`；
- `POST /v1/register` 接受合法负载返回 201，非法负载返回 400 并列出字段级错误；
- 每次调用带 `X-Trace-Id`，账本按 trace 可查；
- `/metrics` 暴露 Prometheus 指标，供共享底座的 `mosaic-dummy` target 抓取。

**一句话验收**：`./test.sh` 全绿，且 `curl` 注册一次后能在账本里按 trace 查到事件。

## 2. 范围与不做

**做**：

- 契约结构校验：必填、类型、枚举、ISO-8601 时间、数组元素类型；
- 从同一份 spec 导出 JSON Schema（校验与文档不两处漂移）；
- dummy 注册 / 回显 / 账本查询 / 指标；
- 标准库实现，零第三方依赖。

**不做**：

- DLQ 与失败重放（归 D3 接入）；
- 鉴权、租户隔离（归 D8/D9）；
- 账本落 PG / 湖表（D1 先用 JSONL，D11 再统一账本）；
- 语义校验：指标口径冲突、权限判定、血缘完整性（归 D6/D7/D8）。

## 3. 技术栈

| 层 | 选择 | 说明 |
|---|---|---|
| 语言 | Python 3.9（系统解释器） | 不装第三方包，`python3` 直接可跑 |
| 契约 | 声明式 spec + 自研校验器 | 见 [`../../infra/kernel/src/mosaic_kernel/contracts.py`](../../infra/kernel/src/mosaic_kernel/contracts.py) |
| 服务 | `http.server.ThreadingHTTPServer` | D1 只做 dummy，不引入 FastAPI |
| 账本 | JSONL（`var/ledger.jsonl`） | 一行一事件：`ts / trace_id / event / detail` |
| 指标 | Prometheus 文本格式 | `/metrics` |

## 4. 系统架构

```text
curl / test
    │  POST /v1/register | /v1/echo
    ▼
DummyService（共享 kernel）
    ├── ContractSet.validate(contract, payload)   ← 本单元 contracts.py（7 契约）
    ├── JsonlLedger.append(trace_id, event, detail) → var/ledger.jsonl
    └── GET /health | /metrics | /v1/contracts | /v1/ledger?trace_id=
```

| 端点 | 作用 |
|---|---|
| `GET /health` | 服务名、版本、契约列表、注册数、uptime |
| `GET /metrics` | `mosaic_service_up` / `requests_total` 等 |
| `GET /v1/contracts` | 7 个契约的 JSON Schema |
| `POST /v1/register` | `{"contract","kind","payload"}` → 201 + trace + digest |
| `POST /v1/echo` | 校验后回显 digest（不落库） |
| `GET /v1/ledger?trace_id=` | 按 trace 查账本事件 |

目录：

```text
P1-contract-kernel/
├── src/mosaic_data_contracts/
│   ├── contracts.py      # 7 个契约的 spec 与样例
│   └── service.py        # 入口：run("data-registry-dummy", ...)
├── tests/                # 14 项（契约 8 + 服务 6）
├── run.sh                # 起 dummy 服务（默认 18180）
└── test.sh               # 跑测试
```

## 5. 前置与复用

- **前置**：共享 D0 底座 [`../../infra/compose/`](../../infra/compose/)（Kafka / PG / Redis / Prometheus / Grafana）；
- **复用**：共享内核 [`../../infra/kernel/src/mosaic_kernel/`](../../infra/kernel/src/mosaic_kernel/)（契约校验、JSONL 账本、dummy HTTP 服务）——AI 平台 D1 用同一套内核，避免两套实现；
- **契约来源**：[通用数据平台建设路线](../../data-platform/通用数据平台建设路线.md) §2.5，字段与验收编号对齐 §6。

## 6. 验收标准

| 编号 | 通过标准 | 当前状态 | 证据 |
|---|---|---|---|
| `V1-1` | 信封 / DLQ schema 冻结 | 🟡 `Envelope` 已冻结；DLQ 归 D3，未实现 | `GET /v1/contracts` 返回 7 个 schema |
| `V1-2` | dummy 源注册 | ✅ | 注册 `TableRef` 返回 201、`registered=true`、trace 头回显 |
| `V1-3` | 一次调用可查 trace + 账本 | ✅ | `/v1/ledger?trace_id=trace-e2e-data-001` 返回 `register.accepted` + `echo.accepted` |

**复现命令**：

```bash
cd engineering/data-platform/P1-contract-kernel
./test.sh                          # 14 项 unittest，实测 5.5s 通过

./run.sh --port 18180 --ledger var/ledger.jsonl &
curl -s -X POST http://127.0.0.1:18180/v1/register \
  -H 'Content-Type: application/json' -H 'X-Trace-Id: trace-e2e-data-001' \
  -d '{"contract":"TableRef","kind":"source","payload":{"catalog":"iceberg","namespace":"ods","table":"vehicle_telemetry"}}'
# → {"trace_id":"trace-e2e-data-001","contract":"TableRef","digest":"sha256:58f5...","registered":true}

curl -s 'http://127.0.0.1:18180/v1/ledger?trace_id=trace-e2e-data-001'
# → {"events":[{"event":"register.accepted",...},{"event":"echo.accepted",...}]}
```

实测摘要（2026-11-11）：

```text
Ran 14 tests in 5.526s
OK
```

Prometheus target `host.docker.internal:18180` 状态 `up`（共享底座已抓取）。

## 7. 实施笔记

- **2026-11-11 新建**：7 契约 + dummy 服务 + 14 项测试；与 AI 平台共用 `mosaic_kernel`，避免两份契约校验器。
- **端口**：默认 `18180`——本机 `18080/18081` 已被其他服务占用，契约内核与共享底座统一改用 `18180/18181`。
- **取舍**：D1 不引第三方依赖（无 pydantic / FastAPI），保证「干净机器 + python3」即可跑；等 D3/D5 接真实链路时再评估是否换 ASGI。
- **待办**：
  1. 账本落 PG（`d0_smoke` 同库），替换 JSONL 的临时方案；
  2. 补 DLQ schema（`V1-1` 的另一半），与 D3 的 `error_code` 枚举对齐；
  3. 契约评审定稿后，把 7 份 schema 导出到 `schemas/`，供外部系统做契约测试；
  4. 接 Kafka 做一次「注册 → 生产 → 消费」的真实链路（D3 起点）。
