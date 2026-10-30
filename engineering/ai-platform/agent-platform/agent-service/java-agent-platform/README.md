# data-agent-java-platform

数据智能助手 Java Spring Boot 控制平面，当前将 Agent 管理、Skill 管理、AgentRun 编排、
MCP Gateway、Sandbox Gateway 和 Redis SSE Gateway 放在一个部署单元内，先打通垂直链路，
后续可以按团队和流量拆分服务。

## 已实现模块

- Agent 控制面：`GET/POST /api/agents`、`GET /api/agents/{id}`、发布接口
- Skill 控制面：`GET/POST /api/skills`、`GET /api/skills/{id}`、发布接口
- AgentRun：`POST /api/agent-runs`、状态、取消；Java 根据 `agentId` 补齐已发布 Snapshot
- Python Runtime Client：调用 `/internal/runs`，使用独立 AK/SK 生成 HMAC-SHA256 签名（本地迁移时才回退 Token）
- SSE 网关：读取 `agent:run:{runId}:events` 并支持 `Last-Event-ID` 查询参数
- MCP Gateway：测试元数据、指标、只读 SQL 校验、知识检索工具
- Sandbox Gateway：Workspace 文件契约和 fail-closed 命令策略
- 持久化切换：`memory` 和 PostgreSQL 两种实现，接口不变

## 前端联调

当前前端页面位于 Python Runtime 示例目录，但已经支持 Java Spring 通信模式：

```bash
cd ../python-agent-runtime/examples
python3 -m http.server 5500
# 浏览器打开 http://127.0.0.1:5500/agent-chat.html
```

页面配置选择“Java Spring SSE（推荐）”，Java 地址填写 `http://127.0.0.1:8080`。
页面会调用：

```text
POST /api/agent-runs
GET  /api/agent-runs/{runId}/events
```

`agent-chat-runtime.html` 是直连 Python Runtime 的调试页面；`agent-chat.html` 是支持
Java Spring、Python Runtime 和演示模式的通用页面。Java 已提供本地 CORS 配置，生产环境请通过
`WEB_ALLOWED_ORIGINS` 限制来源。

## 启动

### 内存模式（不依赖 PostgreSQL）

```bash
cp .env.example .env
set -a; source .env; set +a
mvn spring-boot:run
```

### PostgreSQL 模式

本机 PostgreSQL 已启动且用户/密码可用时：

```bash
export AGENT_PERSISTENCE_MODE=postgres
export POSTGRES_JDBC_URL=jdbc:postgresql://127.0.0.1:5432/postgres
export POSTGRES_USERNAME=postgres
export POSTGRES_PASSWORD=root
mvn spring-boot:run
```

启动时会自动执行 `src/main/resources/db/migration/V1__control_plane.sql`，创建：

- `agent_definition`：Agent Snapshot
- `skill_definition`：Skill 内容或不可变 bundle 地址
- `agent_run`：运行状态、结果和错误
- `audit_event`：AgentRun 接受、Runtime 接受、提交失败和取消请求审计事件

## 测试 Agent / Skill API

```bash
# 创建并发布 Skill；content 和 bundleUrl 必须二选一
curl -X POST http://127.0.0.1:8080/api/skills \\
  -H 'Content-Type: application/json' \\
  -d '{"id":"metadata-analysis","name":"元数据分析","version":"1.0.0","description":"元数据查询规范","content":"# Metadata Skill\\n只使用元数据工具。","requiredTools":["metadata_search","search_metric_definition"]}'

curl -X POST http://127.0.0.1:8080/api/skills/metadata-analysis/publish

# 创建 Agent；snapshot 应符合 Python AgentSnapshot 契约。
curl -X POST http://127.0.0.1:8080/api/agents \\
  -H 'Content-Type: application/json' \\
  -d '{"id":"metadata-agent","name":"元数据分析 Agent","version":1,"status":"DRAFT","snapshot":{}}'

curl -X POST http://127.0.0.1:8080/api/agents/metadata-agent/publish
```

## 设计边界

- Java 负责控制面、租户/权限策略、Snapshot、运行状态、MCP 数据工具、Sandbox Gateway、SSE。
- Python 负责 DeepAgents 推理、Skill 物化、模型调用、MCP/Sandbox Client、Worker 和运行事件。
- Java 默认不执行宿主机命令；`JAVA_SANDBOX_COMMAND_EXECUTION_ENABLED=false` 是 fail-closed 默认值。
- 当前 MCP 工具是本地测试实现；真实元数据、SQL 执行、RAG 检索需替换 `McpToolService` 后端。
- PostgreSQL 仓储已接入基础 Agent/Skill/Run 读写和运行生命周期审计；生产仍需补充正式迁移工具、细粒度租户权限、审计查询 API 和 HA 运维。

## 垂直链路

```text
浏览器 → Java /api/agent-runs → Python Runtime → Redis Event Stream → Java SSE
                                  ↘ Java MCP Gateway
                                  ↘ Java Sandbox Gateway
```
