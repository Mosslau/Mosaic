# data-agent-runtime

本服务是独立、可公共开放的 Python Agent Runtime：任何通过认证且满足准入策略的调用方都可以提交合法 AgentSnapshot，由 Runtime 完成 Snapshot 校验、Agent/Skill/MCP/Sandbox 组装、模型调用、Agent 推理、会话上下文恢复和事件发布。Java Spring Boot 可以作为一个调用方或可选适配层，但不是 Runtime 的启动、构建或执行依赖。

## 架构文档与能力边界

当前 Runtime 的完整架构、实现状态和调用方/Runtime 职责边界见：

- `docs/Python-Agent-Runtime-重构计划.md`（**唯一设计文档，v1.10**：对齐 50 项能力全景；
  三轨排期 12 周；DoD 61 条；附录 G 9 张架构图 + 附录 H 50 项能力矩阵）
- 通用企业级设计标准见仓库根目录 `docs/企业级项目设计参考.md`
- `../docs/Java-Spring与Python-DeepAgents技术架构说明.md`

当前代码已经落地核心执行闭环、AK/SK + HMAC-SHA256 入站认证、Redis 任务队列、独立
Worker、MCP、Skill Artifact、Sandbox Provider、会话恢复和运行事件。真实生产 RAG、摘要跨请求持久化以及 Redis/PostgreSQL/Kubernetes 等生产基础设施验证仍按 P1/P2 继续完善。Runtime 不会在未具备隔离能力时执行宿主机脚本。

## 当前已实现能力

- 公共运行接口：`POST /v1/runs`
- 运行状态查询：`GET /v1/runs/{run_id}`
- 运行取消接口：`POST /v1/runs/{run_id}/cancel`
- Plan 审批接口：`POST /v1/runs/{run_id}/approve`（需要 `runs:approve` Scope）
- 工具级人工确认：快照声明 `interrupt_on` 后，工具执行前中断并发布 `tool_permission_request` 事件
- 恢复执行接口：`POST /v1/runs/{run_id}/resume`（携带人工决策，从 Checkpoint 继续，需要 `runs:approve` Scope）
- 思维链流：推理增量通过 `agent_thinking_delta` 事件下发，与答案增量（`agent_message_delta`）分开
- 附件上传：`POST /v1/files` 返回 `file_id`，Run 通过 `attachments` 引用；支持 CSV/Excel/PDF/文本/图片
- 附件解析：表格与 PDF 转文本注入，图片转多模态块（需模型在 `ALLOWED_VISION_MODELS` 白名单内）
- 结构化输出：快照声明 `response_format`（JSON Schema），终态事件带 `structured` 字段
- 记忆文件：快照声明 `memory_sources`（AGENTS.md 路径），由工作区加载
- 跨会话存储：`AGENT_STORE_BACKEND=none/memory/postgres`，持久化 Agent 的跨 Run 键值数据
- 自评迭代：快照声明 `rubric`（"什么样算完成"），由 `RubricMiddleware` 评分并在未达标时继续改进
- 规划工具：快照 `plan.todo_tool=true` 时启用 `write_todos`，`todos` 随终态事件透出
- 异步子 Agent：快照声明 `async_subagents`（远程 Agent Protocol 服务），受 `ALLOWED_SUBAGENT_HOSTS` 约束
- 运行指标：`OTEL_ENABLED=true` 时通过 OTLP 推送 Run 受理/终态/时延、队列深度、重试/死信、工具调用结果、token 用量
- token 计量：终态事件与状态投影带 `usage`（输入/输出/总计 + 按模型拆分），可直接用于计费与成本分析
- 入口限流：`RATE_LIMIT_RUNS_PER_MINUTE` 按调用方限流，超限返回 429 + `Retry-After`
- 队列背压：`TASK_MAX_QUEUE_DEPTH` 水位触顶时返回 503 + `Retry-After`，拒绝而非丢消息
- 优雅停机：`SHUTDOWN_TIMEOUT_SECONDS` 控制排空在跑 Run 的最长等待
- 存活检查：`GET /v1/health`
- 就绪检查：`GET /v1/ready`（检查 Redis 是否可接收任务）
- DeepAgents Agent Factory
- 任意合法调用方提交的 Agent/Skill/MCP 运行快照
- `langchain-mcp-adapters` MCP Client
- 主 Agent 与 SubAgent 共用 `AgentRuntimeConfig`，SubAgent 编译为 `CompiledSubAgent`
- 根 Agent 与 SubAgent 均支持独立 Sandbox；SubAgent 不继承父 Sandbox，按 `sandbox_scope` 隔离并在 Run 结束统一清理
- OpenAI-compatible 模型适配
- Redis Stream 运行事件发布
- Redis Stream Consumer Group 持久任务队列
- 独立 `data-agent-worker` Agent Worker，Web API 不再直接执行 Agent
- Redis 原子 `run_id` 幂等 Claim、Worker Lease、跨进程 Session Lease
- Principal/租户维度并发配额：Redis ZSET 槽位、心跳续期、TTL 回收和终态释放
- Worker 心跳、Pending 任务自动 reclaim、有限重试和最终失败事件
- Redis 持久化会话消息历史
- 可选的 LangGraph Checkpointer：本地可用 `InMemorySaver`，当前 `.env` 默认配置为 PostgreSQL
- 受控的租户/用户长期记忆读写接口
- 多 AK/SK + HMAC-SHA256 入站认证，支持 Timestamp、Nonce、Body Hash、Principal 映射和生产 HTTPS 强制
- Principal 驱动的 tenant/user/scope 隔离，Run、Session、Memory 和事件查询执行资源所有权校验
- AgentSnapshot Admission：模型、MCP、Skill、SubAgent、步骤、Prompt、Sandbox 资源部署级硬上限
- JSON 日志、Request/Run/Trace Context 传播、OpenTelemetry 和敏感字段脱敏
- Docker、HTTP 和 Kubernetes Sandbox Provider 抽象及统一资源清理

## 会话与记忆模型

- `session_id`：同一轮用户对话的稳定 ID；同一个会话的多次请求必须复用它。
- `run_id`：一次 Agent 执行的唯一 ID，每条用户消息一个。
- LangGraph `thread_id`：运行时使用 `tenant_id:session_id`，避免不同租户意外共用线程。
- Redis 会话历史：保存 `user` 和 `assistant` 消息，支持 Runtime 重启后的历史恢复。
- LangGraph Checkpointer：通过 `CHECKPOINT_BACKEND` 选择实现。当前本地 `.env` 使用 PostgreSQL，测试代码仍可显式注入 `InMemorySaver`。
- 长期记忆：由持有 `memory:write` Scope 的受保护调用方显式写入，Runtime 以受控上下文注入 Prompt。

Runtime 自己维护 Run、Session、Memory 和事件的运行时状态；外部控制面、审计系统或业务数据库可以通过 API/事件流做长期归档，但不是 Runtime 启动、构建和执行的硬依赖。

## 使用 uv

```bash
cd python-agent-runtime
cp .env.example .env
# .env.example 是生产参考配置；启动前必须替换所有 EXAMPLE_ONLY_* 凭证。
# 默认读取 .env 和 .env.local；如需显式选择 .env.prod：
# DATA_AGENT_ENV_FILE=.env.prod uv run data-agent-runtime
# 本地联调可额外创建 .env.local，覆盖 APP_ENV、PUBLIC_MODE、HMAC_REQUIRE_HTTPS
# 和 CHECKPOINT_BACKEND 等配置。
uv sync

# 终端 1：API Producer（只接收请求并写入 Redis Task Stream）
RUNTIME_MODE=api uv run data-agent-runtime

# 终端 2：Agent Worker（独立进程消费队列并执行 DeepAgents）
RUNTIME_MODE=worker uv run data-agent-worker
```

`.env.example` 提供的是生产配置样例，默认使用 PostgreSQL Checkpointer：

```env
CHECKPOINT_BACKEND=postgres
POSTGRES_DSN=postgresql://runtime_checkpoint:<secret>@postgres.example.com:5432/agent_runtime
```

本地单进程联调可以在 `.env.local` 覆盖为 `CHECKPOINT_BACKEND=memory`，不需要启动 PostgreSQL。

服务启动时会自动执行 Checkpointer 的 `setup()`，创建所需的 LangGraph
checkpoint 表。请确保 PostgreSQL 用户、密码和数据库已经存在；生产环境建议使用
单独的数据库或 schema，不要与业务表混用。

如果只做不依赖 PostgreSQL 的单元测试，可以使用：

```env
CHECKPOINT_BACKEND=memory
```

或者：

```bash
uv run uvicorn data_agent_runtime.api:app --reload --port 8800
```

### 本地测试与静态检查

推荐使用统一验证脚本：

```bash
./scripts/verify.sh
```

脚本会运行单元测试、Ruff 和 `git diff --check`。真实 Redis P0 可靠性测试必须显式指定隔离数据库：

```bash
P0_TEST_REDIS_URL='redis://:password@127.0.0.1:6379/15' \
  ./scripts/verify.sh --p0
```

`--p0` 会验证 Redis Stream Pending 接管、Run Lease、Session 串行、并发配额、失败重试和死信；不要指向包含真实业务数据的 Redis 数据库。

```bash
# 普通测试；没有独立 Redis 时，P0 Redis 集成测试会安全跳过
UV_CACHE_DIR=.uv-cache uv run --no-sync pytest -q

# 代码规范和空白检查
UV_CACHE_DIR=.uv-cache uv run --no-sync ruff check src tests examples
git diff --check
```

P0 可靠性测试需要显式配置独立 Redis 数据库，避免误操作开发环境中的运行数据：

```bash
P0_TEST_REDIS_URL='redis://:password@127.0.0.1:6379/15' \
  uv run pytest -q tests/test_p0_reliability.py
```

## 任务队列与 Worker 运行模型

当前生产推荐将 API 和 Agent 执行拆成两个进程：

```text
外部调用方 / 前端
    ↓ HTTP
Python API Producer
    ↓ Redis XADD（原子 run_id Claim）
Redis Stream: agent:tasks
    ↓ Consumer Group / ACK / Pending reclaim
Python Agent Worker
    ↓
DeepAgents / MCP / LLM
    ↓
Redis Event Stream: agent:run:{run_id}:events
```

API 进程不会再使用 `asyncio.create_task()` 执行 Agent，因此 API 重启不会直接丢失尚未消费的任务。Worker 通过 Redis Lease 防止多实例重复执行，通过 Session Lease 保证同一租户会话串行；Worker 异常退出后，Pending 消息会在可见性超时后被其他 Worker reclaim。

多实例启动示例：

```bash
# API 可横向扩展
uv run uvicorn data_agent_runtime.api:app --host 0.0.0.0 --port 8800 --workers 2

# 每个 Worker 使用独立 consumer name；可启动多个进程
uv run data-agent-worker
```

状态流转：

```text
ACCEPTED → RUNNING → COMPLETED
                  ├→ RETRYING → RUNNING
                  ├→ FAILED
                  └→ CANCELLED
```

注意：当前 Retry 是有限次数的队列重投递；Runtime 对外提供 At-least-once 投递、run_id 幂等、Lease/Pending reclaim。外部业务系统可以把事件流归档为自己的最终事实来源，但 Runtime 不要求特定控制面。
Runtime 提供的是 **At-least-once 投递 + run_id 幂等 + Lease/Pending reclaim**，不能宣称
Exactly Once。生产环境还需要结合 Redis/PostgreSQL 高可用、指标、链路追踪和故障演练。

## 运行请求示例

`POST /v1/runs` 始终只负责把序列化的 `RunRequest` 原子写入 Redis Task Stream 并返回 `202 Accepted`；Agent Worker 从 Consumer Group 消费任务。最终答案和运行事件通过按 Run 的 Redis Event Stream 获取。请求中的 `stream` 决定是否发布模型 Token 增量：

### Token 流式

```json
{
  "run_id": "run-stream-001",
  "session_id": "session-001",
  "stream": true,
  "message": "查询最近一个月车辆数量",
  "agent": { "id": "data-analysis-agent", "version": 1 },
  "user_context": { "user_id": "u-001", "tenant_id": "tenant-001" }
}
```

`stream=true` 时，Runtime 使用 DeepAgents/LangGraph 的 `astream_events(version="v2")`，把模型产生的文本增量发布为 `agent_message_delta`；调用方可以从 Redis Stream 读取后转成 SSE，也可以直接使用 Runtime 的 SSE 接口；前端按顺序追加 `payload.delta`。

### 非流式

```json
{
  "run_id": "run-sync-001",
  "session_id": "session-001",
  "stream": false,
  "message": "查询最近一个月车辆数量",
  "agent": { "id": "data-analysis-agent", "version": 1 },
  "user_context": { "user_id": "u-001", "tenant_id": "tenant-001" }
}
```

`stream=false`（默认）时，Runtime 仍使用 DeepAgents 的事件流执行图，但不发布 `agent_message_delta`；这样可以保留 Tool 生命周期事件，最终只发布携带完整 `answer` 的 `run_completed`。

项目中的 `examples/run.json` 是完整的流式请求示例，`examples/run-sync.json` 是完整的非流式请求示例。同一个 `session_id` 发送第二次请求时，Runtime 会加载同一会话的上下文；必须更换 `run_id`，不要更换 `session_id`。

### 本地测试 MCP 和 RAG

当前 `examples/run.json` 默认连接本地测试 MCP Server，不依赖 Java MCP Gateway。测试服务同时提供元数据、指标口径、只读 SQL、SQL 校验和测试 RAG 检索工具。

先启动测试 MCP/RAG 服务：

```bash
cd python-agent-runtime
uv run python examples/test_mcp_server.py
```

默认监听：

```text
http://127.0.0.1:8810/mcp
```

再启动 Runtime 和 Worker：

```bash
uv run data-agent-runtime
uv run data-agent-worker
```

`run.json` 中的 `search_knowledge` 是测试 RAG Retriever，返回固定的本地知识片段；它不访问真实向量库或知识库。生产环境应将 `mcp_servers` 的 URL 替换为受控 MCP/Data Gateway，并将 RAG 工具替换为真实的知识库检索服务。

### 一键启动和停止本地联调栈

也可以使用统一脚本一次启动或停止测试 MCP/RAG、Runtime API、Worker 和前端静态服务：

```bash
cd python-agent-runtime

# 一键启动
./scripts/local-stack.sh start

# 查看状态
./scripts/local-stack.sh status

# 查看日志目录
./scripts/local-stack.sh logs

# 一键停止
./scripts/local-stack.sh stop

# 重启
./scripts/local-stack.sh restart
```

脚本管理的地址：

```text
测试 MCP/RAG：http://127.0.0.1:8810/mcp
Runtime API ：http://127.0.0.1:8800
前端页面    ：http://127.0.0.1:5500/agent-chat-runtime.html
```

进程 PID 和日志位于 `.local/`，停止脚本只会停止由该脚本记录并启动的进程。

### 一键验证完整 Runtime 链路

`local-stack.sh` 只负责启动进程；需要验证 API、HMAC、Redis Stream、Worker、Run 状态、SSE、Session 和 Memory 的完整闭环时，使用端到端脚本：

```bash
# 默认读取项目根目录 .env；启动服务、执行真实模型 Run，并在完成后停止本次启动的栈
./scripts/verify-local-stack.sh

# 验证结束后保留服务，方便继续查看日志或打开前端
./scripts/verify-local-stack.sh --keep

# 服务已经由其他终端启动时，不重复启动进程
./scripts/verify-local-stack.sh --no-start

# 只验证健康检查、HMAC 鉴权、Scope/Principal 隔离和 Memory，不调用真实模型
./scripts/verify-local-stack.sh --smoke

# 使用指定环境文件；脚本不会 source 文件，API、Worker 和验证器都会显式使用它
DATA_AGENT_ENV_FILE=.env.prod ./scripts/verify-local-stack.sh --no-start
```

端到端脚本不会输出任何 Secret Key、模型 API Key、Redis 密码或 PostgreSQL 密码。完整模式会为每个请求生成新的 HMAC Nonce，验证错误签名、Nonce 重放、Scope 拒绝、身份伪造、真实入队、Worker 消费、终态 SSE 自动关闭、重复 `run_id` 幂等、Session 历史和 Memory CRUD；同时会使用官方 MCP Streamable HTTP 客户端完成 `initialize`、`tools/list`、`tools/call`，并实际调用 `search_knowledge` 验证 RAG 返回内容。真实模型或外部 MCP 不可用时，脚本会失败并提示查看 `.local/logs/api.log`、`.local/logs/worker.log`。

### 查询 Run 状态

Runtime 会在 Redis 中维护一份 Run 状态投影，方便任意受保护调用方查询当前状态，不需要扫描完整 Redis Stream：

生产环境和本地环境都必须按上面的 HMAC 签名规则生成请求头。Runtime 不接受固定 Token、
`Authorization: Bearer` 或 Query Token；本地只允许把 HTTPS 校验放宽为 HTTP，不放宽认证协议。
浏览器原生 `EventSource` 不能安全保存 SK，也不能自定义完整签名头，生产应由受保护的
Caller/SSE Gateway 使用 HMAC 连接 Runtime，再向浏览器转发事件。

可能的状态为：

```text
ACCEPTED → RUNNING → COMPLETED
                     ├→ FAILED
                     └→ CANCELLED
```

状态 Key：`agent:run:{run_id}:state`，默认保留 7 天，可通过 `RUN_STATE_TTL_SECONDS` 调整。重复提交已经处于上述状态的 `run_id` 不会在当前 Runtime 中再次执行。生产环境可由外部业务系统归档状态和审计；Runtime 本身仍负责运行时幂等、重试和状态投影。

## 查询会话历史

```bash
curl http://localhost:8800/v1/sessions/session-local-001/messages
```

清理会话历史：

```bash
curl -X DELETE http://localhost:8800/v1/sessions/session-local-001/messages
```

## 管理受控长期记忆

写入一条用户偏好或已审核事实：

```bash
curl -X PUT \
  http://localhost:8800/v1/memories/tenant-local/u-local/default-time-range \
  -H 'Content-Type: application/json' \
  -d '{
    "memory_id": "default-time-range",
    "tenant_id": "tenant-local",
    "user_id": "u-local",
    "memory_type": "preference",
    "key": "default_time_range",
    "content": "最近 30 天"
  }'
```

查询：

```bash
curl http://localhost:8800/v1/memories/tenant-local/u-local
```

删除：

```bash
curl -X DELETE \
  http://localhost:8800/v1/memories/tenant-local/u-local/default-time-range
```

这些是 Runtime 的受保护资源接口，生产环境应由可信后端调用方统一代理或直接使用 HMAC 鉴权，不应把 Secret 下发浏览器。

## Redis Stream 事件

```bash
redis-cli -h 127.0.0.1 -p 6379 -a '<password>' \
  XRANGE agent:run:run-local-001:events - +
```

典型事件：

```text
run_started
agent_started
tool_started
tool_completed
tool_failed
agent_message_delta   # 仅 stream=true
run_completed
run_failed
run_cancelled
```

当前 Runtime 会把流式执行中的模型 Token 和 Tool 生命周期事件转发到 Redis Stream。Tool 事件只携带工具名和调用 ID，不携带完整参数或结果，避免把 SQL、用户数据等敏感内容直接推送到前端。

事件记录的 `event` 字段是 JSON 字符串，核心格式如下：

```json
{
  "run_id": "run-stream-001",
  "event_type": "agent_message_delta",
  "payload": {
    "session_id": "session-001",
    "delta": "正在查询数据"
  },
  "sequence": 3,
  "created_at": "2026-10-23T15:30:00+00:00"
}
```

完成事件携带完整答案：

```json
{
  "event_type": "run_completed",
  "payload": {
    "session_id": "session-001",
    "answer": "最近一个月车辆数量为 128 台。"
  }
}
```

外部 SSE Gateway 转发建议：

```text
XREAD/XREADGROUP agent:run:{run_id}:events
    ↓
解析 event JSON
    ↓
SSE event: agent_message_delta / run_completed
    ↓
浏览器收到 delta 后按 sequence 追加到答案区域
```

本地 Runtime SSE 会把 Redis Stream ID 输出为标准 SSE `id:` 字段，并支持 `Last-Event-ID` 请求头和开发调试参数 `?cursor=<redis-stream-id>`。浏览器断线重连时可以自动携带最后一个事件 ID；自定义 Caller 也可以显式保存并传入该 ID，避免重复或遗漏事件。

SSE 读取到 `run_completed`、`run_failed` 或 `run_cancelled` 后会立即关闭。如果终态事件已经被 Caller 读取、被 Stream 裁剪，或重连游标已经位于终态事件之后，Runtime 会在下一次阻塞读取无新事件时检查 Run State；确认状态为终态后关闭连接，不会无限发送 keep-alive。生产环境的任意 SSE Gateway 都应实现同样的游标恢复和终态关闭逻辑。

前端只在 `stream=true` 时处理 `agent_message_delta`；收到 `run_completed` 后以完整 `answer` 作为最终结果并结束 SSE。非流式调用可以复用同一套 SSE，也可以等待 `run_completed` 后由普通查询接口读取最终结果。Redis Stream 只负责实时运行事件，不是用户历史消息的唯一来源。

## 当前限制与未完成项

1. Runtime 已提供正式的 Run、Session、Memory、SSE 和审计事件接口；外部控制面可按需实现业务侧 REST/SSE、持久化和审计归档，但不是 Runtime 的必需组件。
2. `CHECKPOINT_BACKEND=postgres` 时，完整 LangGraph 图状态由 PostgreSQL 持久化；`memory` 模式的 `InMemorySaver` 只适合本地开发和单元测试。
3. 生产环境仍需要完成 Redis/PostgreSQL 高可用、多实例部署、Checkpoint 保留周期和清理策略验证。
4. Runtime 的队列是 At-least-once 模型，虽然已实现 `run_id` 幂等、Lease、Pending reclaim、有限重试和死信，但不能承诺 Exactly Once。
5. P0 Redis 可靠性测试需要配置独立的 `P0_TEST_REDIS_URL`；普通测试未连接真实 Redis 时会跳过这组集成测试。
6. Plan 已支持规则、最大步骤限制和 `PENDING_APPROVAL` 审批入队；步骤级持久化和复杂审批编排仍需后续扩展。
7. RAG 当前通过 MCP 调用外部检索工具；仓库中的 `search_knowledge` 只是固定测试服务，不包含生产向量库、Embedding、Reranker 或权限过滤。
8. 摘要中间件和 `persist_summary` 配置已经接入，但跨请求摘要持久化、恢复、版本和清理策略仍需补齐。
9. Docker、HTTP 和 Kubernetes Sandbox Provider 已实现，但真实 Kubernetes 集群、远程 Sandbox Gateway、镜像准入和资源隔离尚未完成生产联调。
10. OpenTelemetry、Trace Context 和脱敏日志已实现，但 OTel Collector/Jaeger/Tempo 等外部观测基础设施尚未在当前仓库中完成真实验证。
11. MCP Server 必须由受控服务提供；Python Runtime 不直接访问业务数据库。任意实现 MCP 契约的 Tool/Data Gateway 都可以接入，Java Gateway 只是其中一种可替换部署方式。

## 前端对话原型

新增页面：

```text
examples/agent-chat.html
```

它提供一个不依赖构建工具的 Agent 对话页面，可以查看当前已发布 Agent、模型、Skill、工具和会话信息，并支持：

- Token 流式 / 非流式切换
- 会话 ID、用户 ID、租户 ID 配置
- 受控 SSE Gateway / Python Runtime / 本地演示三种通信方式
- Agent 运行状态和错误提示
- 流式 Token 增量拼接
- `run_completed` 完整答案校正

直接预览：

```bash
cd python-agent-runtime/examples
python3 -m http.server 5500
```

然后打开 `http://127.0.0.1:5500/agent-chat.html`。页面默认使用本地 Python Runtime 联调链路：

```text
POST /v1/runs
GET  /v1/runs/{run_id}/events
```

Python 的 SSE 地址是一个只读开发桥接，由 Runtime 从 Redis Stream 读取事件，方便本地页面直接查看 Token。生产环境可以切换为任意受控 SSE Gateway：

```text
POST /api/agent-runs
GET  /api/agent-runs/{run_id}/events
```

如果外部 SSE 接口路径不同，可以点击页面右上角的配置按钮修改 Base URL 和 SSE URL 模板。没有后端时可以切换到“本地演示模式”检查页面交互。Python 的开发 SSE 桥接不直接暴露 Redis，生产部署时应由受保护的调用方负责对外鉴权、业务审计和协议适配；也可以直接使用 Runtime 的 HMAC API。

## Agent Snapshot 最终演进

`AgentSnapshot` 是调用方和 Python Runtime 之间的不可变运行契约。一次
Agent Run 使用一份固定快照，不在运行过程中重新读取 Agent 或 Skill 配置。

```json
{
  "id": "data-analysis-agent",
  "version": 3,
  "name": "数据分析助手",
  "system_prompt": "负责车辆域数据分析",
  "model": {
    "provider": "deepseek",
    "name": "deepseek-chat",
    "temperature": 0.1
  },
  "skills": [
    {
      "id": "vehicle-analysis",
      "version": "1.3.0",
      "bundle_url": "https://object-storage.example/skills/vehicle-analysis-1.3.0.tar.gz",
      "sha256": "<64-character-sha256>",
      "size_bytes": 18342,
      "entry_path": "skills/vehicle-analysis",
      "required_tools": ["metadata_search", "sql_validate"]
    }
  ],
  "subagents": [
    {
      "name": "metadata-agent",
      "description": "负责指标和元数据查询",
      "skill_ids": ["metadata-analysis"],
      "tool_allowlist": ["metadata_search", "search_metric_definition"]
    }
  ],
  "mcp_servers": [],
  "plan": {
    "enabled": true,
    "require_approval": false,
    "max_steps": 10,
    "allow_replan": true
  },
  "compression": {
    "enabled": true,
    "trigger_tokens": 24000,
    "keep_recent_messages": 12,
    "summary_max_tokens": 3000,
    "persist_summary": true
  },
  "rag": {
    "enabled": true,
    "tool_allowlist": ["search_knowledge"]
  },
  "workspace": {
    "enabled": true,
    "workspace_id": "ws-001",
    "read_only": true,
    "allowed_paths": []
  },
  "sandbox": {
    "enabled": false,
    "network_mode": "none",
    "timeout_seconds": 60,
    "allow_commands": []
  },
  "max_steps": 20
}
```

### Skill Artifact 加载

生产环境推荐调用方提交 `bundle_url + version + sha256`，而不是把完整 Skill 文本放在
请求中。Python Runtime 会：

```text
下载 bundle
  → 限制大小
  → 校验 SHA256
  → 防目录穿越安全解压
  → 写入 Skill Cache
  → 复制到本次 Run 的 workspace
  → FilesystemBackend(root_dir=workspace)
  → create_deep_agent(skills=["/skills"])
```

Skill 包必须包含如下结构：

```text
skills/
└── vehicle-analysis/
    ├── SKILL.md
    ├── references/
    ├── scripts/
    └── templates/
```

`SKILL.md` 应包含符合 Agent Skills 约定的 YAML frontmatter，例如：

```markdown
---
name: vehicle-analysis
description: 两轮车车辆域数据分析能力
compatibility: data-agent-runtime
---

# Vehicle Analysis Skill
```

本地开发仍兼容旧格式的 `content` 字段，Runtime 会把它转换成临时的原生 Skill
目录；生产配置应使用不可变对象存储地址。相关配置项：

```env
SKILL_CACHE_DIR=/tmp/data-agent-runtime/skill-cache
WORKSPACE_ROOT=/tmp/data-agent-runtime/workspaces
SKILL_DOWNLOAD_TIMEOUT_SECONDS=30
SKILL_MAX_BUNDLE_BYTES=52428800
SKILL_MAX_EXTRACTED_BYTES=209715200
SKILL_MAX_FILES=2000
SKILL_ALLOWED_HOSTS=ks3.example.com
SKILL_ALLOW_HTTP_LOCAL=true
```

生产环境必须配置 `SKILL_ALLOWED_HOSTS`，只允许从已登记的 KS3/S3-compatible
对象存储主机下载 Skill；Runtime 不跟随跨主机重定向，也不会接受 URL 中的账号密码。

Skill Bundle 下载支持可选的部署侧 AK/SK：

```env
SKILL_ARTIFACT_ACCESS_KEY=skill-artifact-prod
SKILL_ARTIFACT_SECRET_KEY=<从 Secret Manager 注入>
```

两项同时配置时，Runtime 使用与入站认证一致的 `DATA_AGENT-HMAC-SHA256` 请求签名访问
对象存储适配层或 Artifact Gateway；两项均未配置时，直接拉取 HTTPS 公开 URL 或预签名 URL。
只配置其中一项会 fail closed。对象存储或网关必须支持该 HMAC 请求头协议；原生 AWS S3、
阿里云 OSS 等如果使用各自的签名协议，应接入对应的对象存储适配器或先生成预签名 URL，
不能把 Secret 直接作为普通 HTTP Header 发送。

### Runtime API 认证（AK/SK + HMAC-SHA256）

除 `/v1/health` 外，Runtime 的接口统一使用独立的 AK/SK 请求签名；SK 永远不通过网络传输。
Runtime 只读取多调用方注册表，每个调用方都拥有独立的 AK/SK、Principal、Tenant 和 Scope：

```env
INTERNAL_SERVICE_CREDENTIALS_JSON=[{"access_key":"caller-a","secret_key":"<从 Secret 注入>","principal_id":"principal-a","tenant_id":"tenant-a","roles":["runtime:caller"],"scopes":["runs:write","runs:read"]}]
```

不支持 `INTERNAL_SERVICE_ACCESS_KEY` / `INTERNAL_SERVICE_SECRET_KEY` 单凭证配置，也不支持默认
Principal；需要新增调用方时，应在注册表中新增独立对象并保证 `access_key` 唯一。

生产环境每个请求必须通过 HTTPS；本地 `APP_ENV=local`、`dev`、`development` 或 `test`
联调允许使用 HTTP。配置项 `HMAC_REQUIRE_HTTPS` 默认值为 `true`，生产环境必须保持为
`true`；即使误设为 `false`，生产 Runtime 也会 fail closed，不会放行 HTTP 请求。

除公开的 `/v1/health` 外，受保护接口必须携带以下请求头：

```http
X-Access-Key: <access-key>
X-Timestamp: <Unix seconds>
X-Nonce: <cryptographically-random nonce>
X-Content-SHA256: <lowercase hex SHA-256 of raw body>
X-Signature-Version: DATA_AGENT-HMAC-SHA256
X-Signature: <base64url(HMAC-SHA256)>
```

签名的 Canonical Request（字段之间使用 `\n`）为：

```text
DATA_AGENT-HMAC-SHA256
{access_key}
{timestamp}
{nonce}
{HTTP_METHOD_UPPERCASE}
{path}
{canonical_query}
{sha256(raw_body)}
```

Query 参数按名称和值排序、保留空值并使用 UTF-8 percent encoding；JSON Body 必须先确定性序列化，
再计算 Body Hash。Runtime 默认只接受 ±300 秒时间窗口，并在 Redis 中以
`agent:auth:nonce:{access_key}:{nonce}` 使用 `SET NX EX` 原子占用 Nonce，防止重放。

所有部署都必须配置非空的 `INTERNAL_SERVICE_CREDENTIALS_JSON`、Redis 和 HMAC 参数；
生产环境还必须启用 HTTPS。注册表缺失、格式错误、重复 AK 或字段不完整时 fail closed。
Runtime 不接受固定 Token、`Authorization: Bearer` 或 query token。不要把任何 SK 下发浏览器、
写入日志或提交 Git。

本地联调示例（仅演示签名，不要把真实 Secret 提交到代码仓库）：

```bash
python - <<'PY'
import hashlib, hmac, base64, time, uuid, urllib.parse, os

# 由调用方从自己的 Secret 管理系统读取注册表中对应调用方的 AK/SK。
access_key = os.environ["CALLER_ACCESS_KEY"]
secret_key = os.environ["CALLER_SECRET_KEY"].encode()
method, path, query, body = "GET", "/v1/runs/run-stream-001", "", b""
timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
canonical = "\n".join([
    "DATA_AGENT-HMAC-SHA256", access_key, timestamp, nonce, method, path, query,
    hashlib.sha256(body).hexdigest(),
])
signature = base64.urlsafe_b64encode(
    hmac.new(secret_key, canonical.encode(), hashlib.sha256).digest()
).rstrip(b"=").decode()
print(f"curl -H 'X-Access-Key: {access_key}' \
  -H 'X-Timestamp: {timestamp}' -H 'X-Nonce: {nonce}' \
  -H 'X-Content-SHA256: {hashlib.sha256(body).hexdigest()}' \
  -H 'X-Signature-Version: DATA_AGENT-HMAC-SHA256' \
  -H 'X-Signature: {signature}' http://127.0.0.1:8800/v1/runs/run-stream-001")
PY
```

本地 standalone SSE 页面无法安全持有 SK，因此仅在 `APP_ENV=local` 使用本地迁移 Token；
生产 SSE 应由受保护的调用方完成 HMAC 鉴权后访问 Runtime。

### SubAgent、Workspace 和压缩

- `subagents` 会转换成 DeepAgents 原生声明式 `SubAgent`，可绑定 Skill 和 MCP 工具白名单。
- `workspace.enabled=true` 时使用本次 Run 独立目录和 `FilesystemBackend`；`read_only=true`
  会拒绝文件写入工具。
- `compression` 会替换 DeepAgents 默认摘要中间件，以使用快照下发的
  `trigger_tokens`。`keep_recent_messages` 和 `persist_summary` 已进入契约，持久化摘要策略仍可由 Runtime 的 Checkpointer 或外部业务中间件补齐。
- `rag.tool_allowlist` 用于校验 MCP/Data Gateway 是否提供配置的检索工具；RAG 数据库和权限由 MCP 服务提供方负责。
- `plan` 会注入运行规则和最大计划步数；`require_approval=true` 时进入 `PENDING_APPROVAL`，持有 `runs:approve` Scope 的调用方审批后才入队。
- `sandbox.enabled=true` 时，Python Runtime 会加载 `sandbox_write_file`、`sandbox_run`、
  `sandbox_read_file` 和 `sandbox_collect_artifact`，这些 Tool 只依赖 `SandboxProvider`；
  当前默认是 HTTP Provider，可连接任意实现相同契约的 Sandbox Gateway 或 Sidecar。
- `SANDBOX_PROVIDER=http` 表示通用 HTTP Sandbox 契约：任何实现该契约的网关都可接入，
  Runtime 不内置任何以具体控制面命名的取值（历史名称 `java_gateway` 已移除，误配会直接报错）。
- 未配置 `SANDBOX_GATEWAY_BASE_URL` 时仍会 fail closed，不会退化为宿主机 Shell 执行。
- Sandbox Gateway 的 HTTP 契约以实现为准：`src/data_agent_runtime/clients/sandbox.py`；端口语义见重构计划 §3.7。

## 公共 Agent Runtime 重构说明

截至 2026 年 10 月 27 日，Runtime 的正式目标契约是“独立执行服务”，而不是某个控制面内部的执行插件：

```text
任意合法 AgentSnapshot + 调用方 AK/SK
        ↓ HMAC Authentication
Principal（tenant / subject / roles / scopes / quota）
        ↓ Snapshot Admission
/v1/runs → Redis Stream → 独立 Worker → DeepAgents / Model / MCP / Skill / Sandbox
        ↓
Run State + Event Stream + Session/Memory
```

### 调用方身份和多租户边界

生产环境推荐使用 `INTERNAL_SERVICE_CREDENTIALS_JSON` 注册多组独立 AK/SK。Secret Key 只通过 Secret 注入，不能放进请求体、前端或日志。认证成功后 Runtime 将 AK 映射为 Principal：

- `principal_id`：调用方或应用身份；
- `tenant_id`：租户边界；
- `subject_id`：用户/主体边界，可选；
- `roles`、`scopes`：接口授权边界；
- `quotas`：步骤数、超时和并发等调用方配额。

请求中的 `user_context` 不再是可信身份来源。它只能作为兼容字段；如果提供的 tenant/user 与认证 Principal 不一致，Runtime 直接拒绝。未提供时，Runtime 根据 Principal 自动构造可信运行上下文。

### Snapshot 准入和资源安全

Pydantic 负责结构校验，`runtime/admission.py` 负责部署级策略校验。最终允许的资源不能超过部署和 Principal 配额，包括：模型 Provider/名称、Prompt 大小、Skill/MCP/Tool 数量、SubAgent 深度、最大步骤、Sandbox 超时/输出/进程/CPU/内存/磁盘和网络模式。公共模式下：

- 禁止 stdio MCP 和任意本地命令执行；
- MCP HTTP 地址必须满足 HTTPS、Host Allowlist，并阻止私网/Loopback/保留地址；
- MCP 不允许在 Snapshot 中携带内联 Secret Header，应使用服务端 `credential_ref`；
- 禁止 inline Skill，Skill 必须使用不可变 Bundle URL + SHA-256；
- Sandbox `network_mode=full` 被拒绝，镜像和资源必须满足部署 Allowlist。

### 会话隔离

公共模式的 Redis Session Key 同时包含 `tenant_id`、`user_id` 和 `session_id` 的摘要，避免不同租户使用相同会话 ID 时发生上下文串读。API 读取 Run、事件、Session 和 Memory 前都会执行 Principal 所有权校验。

### API 版本

公共契约使用 `/v1/*`：

- `GET /v1/health`
- `GET /v1/ready`
- `POST /v1/runs`
- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/events`
- `POST /v1/runs/{run_id}/cancel`
- `POST /v1/runs/{run_id}/approve`（`plan.require_approval=true` 时使用）
- `/v1/sessions/*`
- `/v1/memories/*`

Runtime 公共接口统一使用 `/v1/*`，不依赖 Java 控制面。

### 多 AK/SK 配置示例

```env
APP_ENV=production
PUBLIC_MODE=true
INTERNAL_SERVICE_CREDENTIALS_JSON=[{"access_key":"caller-a","secret_key":"注入的Secret","principal_id":"principal-a","tenant_id":"tenant-a","subject_id":"user-a","roles":["agent:caller"],"scopes":["runs:write","runs:read","runs:cancel","runs:approve","sessions:read","sessions:write","memory:read","memory:write"],"quotas":{"max_steps":20,"run_timeout_seconds":300,"max_concurrent_runs":20}}]
```

Runtime 不提供单调用方 AK/SK fallback。所有调用方都必须通过 `INTERNAL_SERVICE_CREDENTIALS_JSON`
注册，并使用独立的 AK/SK、Principal、Tenant 和 Scope。MCP 的 `credential_ref` 由 Runtime 从部署侧
`MCP_CREDENTIALS_JSON` 解析，Snapshot 不携带 MCP Secret。

### 当前边界

Runtime 的 Redis Stream 仍是至少一次投递语义；`run_id` 幂等、Lease 和 Pending reclaim 用于抑制重复执行，但不能宣称 Exactly Once。当前 Model Provider Registry 已明确支持 `openai`、`openai-compatible` 和 `deepseek`，其中 `deepseek` 复用 OpenAI-compatible 适配器；新增 Provider 必须同时实现适配器、凭证配置、Admission 注册和测试。`ALLOWED_MODEL_PROVIDERS` 只控制部署白名单，不会动态安装适配器。Snapshot 未显式提供模型温度时使用 `MODEL_TEMPERATURE`，显式传值时以 Snapshot 为准。MCP 凭证当前通过部署侧 `MCP_CREDENTIALS_JSON` 引用，生产环境建议替换为 Vault/KMS/Secret Manager 适配器。公共 Admission 会选择拒绝不安全配置，而不是静默放行。
