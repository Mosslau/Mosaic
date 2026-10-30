# DataAgentPlat · 数据智能助手平台

面向两轮车数据治理与数据分析场景的 Agent 平台，采用 **Java Spring Boot 控制面 + Python DeepAgents 智能运行时** 的双栈架构：

- **Java 控制面**：Agent / Skill 管理、运行快照、权限与审计、MCP 数据工具网关、Sandbox 网关、SSE 网关，是业务配置与运行记录的权威来源。
- **Python 运行时**：Prompt 与 Skill 组装、模型调用、工具循环、子 Agent 编排、会话恢复、长期记忆，独立部署、可被任意合法调用方接入。

> 核心原则：**Java 决定"能不能用、能用到什么程度"，Python 决定"下一步该调什么工具"**。模型输出永远不作为权限、租户或身份的可信来源。

## 架构总览

```text
浏览器 / 外部调用方
        │  REST / SSE
        ▼
┌─────────────────────────────────────────────┐
│ Java Spring Boot 控制面 :8080                │
│ Agent / Skill / Run Snapshot / 权限 / 审计    │
│ MCP 工具网关 · Sandbox 网关 · SSE 网关        │
└───────────────┬─────────────────────────────┘
                │ HTTP + AK/SK HMAC-SHA256
                ▼
┌─────────────────────────────────────────────┐
│ Python Runtime API :8800                     │
│ 认证 → Snapshot 准入 → 写入 Redis 任务流      │
└───────────────┬─────────────────────────────┘
                │ Redis Stream: agent:tasks
                ▼
┌─────────────────────────────────────────────┐
│ Agent Worker（独立进程，可横向扩展）           │
│ DeepAgents 推理循环                           │
├── MCP Client ─────→ 数据工具网关               │
├── Sandbox ────────→ Docker / Kubernetes       │
└── LLM ────────────→ DeepSeek / OpenAI 兼容     │
└───────────────┬─────────────────────────────┘
                │ Redis Stream: agent:run:{run_id}:events
                ▼
        SSE 推送 / 运行状态查询 / 审计归档
```

职责边界：

| 问题 | 负责方 |
|---|---|
| 用户是否有权限使用某个 Agent | Java |
| Agent 当前发布版本、Skill 是否已发布 | Java |
| 某张表能否访问、SQL 是否允许执行 | Java |
| 下一步调用什么工具、如何循环推理 | Python |
| Prompt / Skill / MCP / Sandbox 如何组装 | Python |
| 会话消息、Run 结果、审计是否落库 | Java（Runtime 也保留运行态） |
| Checkpoint 与上下文恢复 | Python |

## 仓库结构

```text
DataAgentPlat/
├── java-agent-platform/          # Java 17 + Spring Boot 3.4 控制面（Maven）
│   ├── src/main/java/...         # Agent/Skill/Run API、MCP/Sandbox 网关、HMAC、持久化
│   ├── src/main/resources/
│   │   ├── application.yml       # 端口、Redis、Runtime 地址、持久化模式
│   │   └── db/migration/         # PostgreSQL 建表脚本（postgres 模式自动执行）
│   └── .env.example              # 全部可配置环境变量
├── python-agent-runtime/         # Python 3.12 + DeepAgents 运行时（uv 管理）
│   ├── src/data_agent_runtime/   # api / runtime / clients / tools / prompts
│   ├── tests/                    # 单元测试与 P0 可靠性测试
│   ├── examples/                 # 联调页面、测试 MCP Server、示例请求
│   ├── scripts/                  # 本地栈启停、端到端验证、文档检查
│   └── docs/                     # Runtime 架构与能力说明
├── docs/                         # 平台级架构说明
└── resources/db/migration/       # 早期 SQL 副本（正式脚本以 Java 模块内为准）
```

## 快速开始

### 前置条件

| 依赖 | 版本 | 说明 |
|---|---|---|
| JDK | 17+ | 运行 Java 控制面 |
| Maven | 3.9+ | 构建 Java 控制面 |
| Python | 3.12 | 运行时版本在 `.python-version` 中锁定 |
| uv | 最新 | 安装与运行 Python 依赖 |
| Redis | 7+ | 任务队列、事件流、会话与配额（必需） |
| PostgreSQL | 14+ | LangGraph Checkpoint 与 Java 控制面持久化（可选，本地可用 memory 模式） |
| Docker | 可选 | Docker Sandbox Provider |

### 方式一：只跑 Python Runtime（最快体验）

```bash
cd python-agent-runtime
cp .env.example .env          # 生产参考配置，必须替换所有 EXAMPLE_ONLY_* 占位值
uv sync

# 本地裸机联调需要 HTTP（非 HTTPS）时，新建 .env.local 覆盖：
#   APP_ENV=local
#   PUBLIC_MODE=false
#   HMAC_REQUIRE_HTTPS=false
#   CHECKPOINT_BACKEND=memory

# 终端 1：API（只认证、准入、入队）
RUNTIME_MODE=api uv run data-agent-runtime

# 终端 2：Worker（消费队列、执行 Agent）
RUNTIME_MODE=worker uv run data-agent-worker
```

也可以一键拉起完整的本地联调栈（API :8800、Worker、测试 MCP :8810、前端 :5500）：

```bash
cd python-agent-runtime
./scripts/local-stack.sh start
./scripts/local-stack.sh status
./scripts/local-stack.sh logs
./scripts/local-stack.sh stop
```

### 方式二：Java 控制面 + Python Runtime

```bash
# 先按方式一启动 Python API 与 Worker
cd java-agent-platform
cp .env.example .env
set -a; source .env; set +a
mvn spring-boot:run
```

默认使用内存持久化，适合本地冒烟；需要落库时：

```bash
export AGENT_PERSISTENCE_MODE=postgres
export POSTGRES_JDBC_URL=jdbc:postgresql://127.0.0.1:5432/postgres
export POSTGRES_USERNAME=postgres
export POSTGRES_PASSWORD=***
mvn spring-boot:run
```

启动时会自动执行 `src/main/resources/db/migration/V1__control_plane.sql`。

### 前端联调

`python-agent-runtime/examples/` 下有两个页面，均支持「Java SSE / Python Runtime / 演示模式」切换：

```bash
cd python-agent-runtime/examples
python3 -m http.server 5500
# 浏览器打开 http://127.0.0.1:5500/agent-chat.html
```

## 接口一览

### Python Runtime（`/v1`，除健康/就绪检查外均需 HMAC 认证）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/v1/health` | 存活检查 |
| GET | `/v1/ready` | 就绪检查（Redis 可接收任务） |
| POST | `/v1/runs` | 提交 Run，返回 `202 Accepted` |
| GET | `/v1/runs/{run_id}` | 查询运行状态 |
| GET | `/v1/runs/{run_id}/events` | SSE 事件流，支持 `Last-Event-ID` 续读 |
| POST | `/v1/runs/{run_id}/approve` | 审批等待中的 Run（需 `runs:approve`） |
| POST | `/v1/runs/{run_id}/cancel` | 请求取消 |
| GET / DELETE | `/v1/sessions/{session_id}/messages` | 会话历史读取 / 清空 |
| GET / PUT / DELETE | `/v1/memories/{tenant_id}/{user_id}[/{memory_id}]` | 长期记忆受控读写 |

### Java 控制面

| 方法 | 路径 | 说明 |
|---|---|---|
| GET / POST | `/api/agents` | 列出 / 保存 Agent 草稿 |
| GET | `/api/agents/{id}` | 查询 Agent |
| POST | `/api/agents/{id}/publish` | 发布 Agent（快照编译 Skill） |
| GET / POST | `/api/skills` | 列出 / 保存 Skill |
| GET | `/api/skills/{id}` | 查询 Skill |
| POST | `/api/skills/{id}/publish` | 发布 Skill |
| POST | `/api/agent-runs` | 提交运行（补齐已发布快照后转发 Runtime） |
| GET | `/api/agent-runs/{runId}` | 运行状态 |
| POST | `/api/agent-runs/{runId}/cancel` | 取消运行 |
| GET | `/api/agent-runs/{runId}/events` | SSE 事件流（`Last-Event-ID`） |
| POST | `/mcp`、`/internal/mcp` | MCP 数据工具网关（JSON-RPC） |
| POST | `/internal/sandboxes/**` | Sandbox 网关（创建 / 文件 / 命令 / 产物） |

## 一次 Run 的生命周期

1. 调用方携带 AK/SK 签名提交 `POST /v1/runs`（或经 Java `/api/agent-runs` 补齐快照后转发）。
2. Runtime 校验时间戳、Nonce、Body Hash，绑定 Principal，并执行 **AgentSnapshot 准入**（模型、MCP、Skill、子 Agent 深度、Sandbox 资源的部署级上限）。
3. 写入 Redis Stream `agent:tasks`，立即返回 `202`；`run_id` 幂等。
4. Worker 通过 Consumer Group 消费，获取 Run Lease 与 Session Lease，构建 DeepAgents 执行。
5. 执行过程把 Token 增量、工具生命周期、最终答案写入 `agent:run:{run_id}:events`。
6. 终态后 ACK；失败按次数重试或进入死信流。语义为 **At-least-once + run_id 幂等**，不是 Exactly-once。

## 配置与密钥

- 所有本地配置放在 `.env`，已被 `.gitignore` 排除；仓库只提交 `.env.example`。
- `.env.example` 中的 `EXAMPLE_ONLY_*` 全部是占位值，生产必须由 Secret Manager 注入。
- Runtime 入站认证使用 AK/SK + HMAC-SHA256（Timestamp + Nonce + Body Hash），生产强制 HTTPS；Redis 不可用时 Nonce 防重放会 fail-closed。
- Java 内部接口（`/mcp`、`/internal/**`）同样要求 HMAC 或内部 Token，不要在生产保留本地示例值。
- Sandbox 默认关闭命令执行（`JAVA_SANDBOX_COMMAND_EXECUTION_ENABLED=false`），Python 侧不在宿主机直接执行调用方命令。

## 测试与验证

```bash
# Python：单元测试 + Ruff + 中文文档字符串检查
(cd python-agent-runtime && ./scripts/verify.sh)

# 真实 Redis 的 P0 可靠性测试（Pending 接管、租约、并发配额、重试、死信）
(cd python-agent-runtime && P0_TEST_REDIS_URL='redis://:password@127.0.0.1:6379/15' ./scripts/verify.sh --p0)

# 端到端联调栈验证（会启动 API/Worker/测试 MCP/前端）
(cd python-agent-runtime && ./scripts/verify-local-stack.sh)

# Java：编译 + 单元测试
(cd java-agent-platform && mvn test)
```

## 当前状态与已知问题

| 模块 | 状态 |
|---|---|
| Python Runtime | ✅ P0 闭环可用：HMAC 认证、准入、队列、Worker 租约、Sandbox、会话/记忆、事件流、可观测性 |
| Java 控制面 | ⚠️ 骨架：Agent / Skill / Run 主链路完整，MCP 工具与 Sandbox 命令执行为桩实现 |
| Java → Python 调用 | ❌ 契约尚未对齐，端到端链路待打通（见下） |
| 生产基础设施 | ⏳ Redis HA、PostgreSQL Checkpointer、Kubernetes Sandbox、真实 RAG/MCP 尚未验证 |

**待修复的 P0（Java ↔ Python 契约）**

1. 路径不一致：Java 调用 `/internal/runs`，Runtime 现为 `/v1/runs`。
2. 字段命名不一致：Java record 序列化为 camelCase，Runtime 只接受 snake_case。
3. SSE 事件名不一致：Java 固定发 `agent_event`，前端监听 `agent_message_delta` / `run_completed`。

**其他注意点**

- 从别的目录拷贝过来的 `.venv` 会保留旧的 editable 路径，需重新 `uv sync`。
- 本地 `.env` 若设置 `HMAC_REQUIRE_HTTPS=false`，`tests/test_auth.py` 会因配置串扰失败，可用 `HMAC_REQUIRE_HTTPS=true uv run pytest` 复现干净结果。

## 文档

- [平台总体架构（Java + Python 边界、协议、SQL 安全、实施计划）](docs/Java-Spring与Python-DeepAgents技术架构说明.md)
- [企业级项目设计参考（6 个内部结构 + 13 个外部能力，含 30 项评审清单）](docs/企业级项目设计参考.md)
- [Agent 服务能力与扩展点全景（9 域 50 项能力、7 个端口、12 条扩展轴）](python-agent-runtime/docs/Agent%20服务能力与扩展点全景.md)
- [Python Runtime 重构计划（唯一设计文档）](python-agent-runtime/docs/Python-Agent-Runtime-重构计划.md)
- [Java 控制面说明](java-agent-platform/README.md)
- [Python Runtime 使用说明](python-agent-runtime/README.md)

> 产品原型 `docs/index_v3.4.html` 体积较大，未纳入版本库，仅在本地保留。
