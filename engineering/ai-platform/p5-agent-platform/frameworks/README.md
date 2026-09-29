# 🏗️ AgentNest 平台底座（Platform Base）— 统一架构总纲

> **一句话主线**：把 `frameworks/` 四条框架路线与 `agent-core/` 自研路线，统一到**一个平台底座 + 可插拔运行时**的架构上——公共层（接入 / 控制面 / AI 基础设施）只建一次，各框架与自研内核都以"运行时适配器"接入，按能力矩阵差异化供给。
>
> 版本：v0.2 · 状态：评审稿 · 日期 2026-08-27

---

## 0. 为什么需要"统一底座"

仓库此前的定位是**两条并列路线**：`frameworks/`（选型框架、快速平台化）与 `agent-core/`（完全自研、深度可控）。但两条路线共享了 80% 的公共建设：

- 接入层（Web / 企微 / 飞书 / CLI / IDE / Open API）
- 控制面（租户 / RBAC / Hub / 发布 / 审计 / 计量）
- AI 基础设施（模型网关 / 凭证 / MCP 网关 / 沙箱 / 可观测 / 数据）

分别建设 = 重复造轮子；且 Agent 运行时（循环 / 工具 / 策略 / 路由）恰恰是各框架与自研内核**差异最大、最值得隔离替换**的部分。因此把架构收敛为：

```
        一个平台底座（公共层，建一次）
              │ 只依赖运行时端口
              ▼
   运行时适配层（Runtime Port & Adapter）
   ┌──────────┬──────────┬──────────┬──────────┬───────────┐
   │ agentscope│ langchain│  codex   │   dsh    │ agent-core│
   │ -adapter │ -graph   │ -adapter │ -adapter │ -adapter  │
   │          │ -adapter │ (闭源)   │          │ (自研Rust)│
   └──────────┴──────────┴──────────┴──────────┴───────────┘
```

**agent-core 不再是"并列路线"，而是底座的第五个（也是唯一自研、最可控的）运行时适配器。** 其《技术架构方案》同时是"自研运行时"的设计蓝本。

---

## 1. 架构全景

```
┌──────────────────────────────────────────────────────────────────────┐
│                    接入层（公共 · 框架无关）                            │
│  Web Admin │ Web 用户端 │ 企微/飞书 │ IM │ CLI │ IDE 插件 │ Open API  │
└───────────────────────────┬──────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      平台控制面（公共 · 框架无关）                      │
│  租户/用户/RBAC │ Hub 资源库 │ Agent 模板与发布 │ 渠道适配器集群          │
│  审批中心 │ 审计/计量/配额/计费 │ 运行时注册表 │ 能力矩阵校验             │
└───────────────────────────┬──────────────────────────────────────────┘
                            ▼ 发布物化（release 快照 · 运行时无关）
┌──────────────────────────────────────────────────────────────────────┐
│                运行时适配层 Runtime Port & Adapter（公共）              │
│  统一契约：会话生命周期 · StreamEvent 事件流 · 审批挂起 · 隔离翻译        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────┐ │
│  │ agentscope │ │ langchain- │ │   codex    │ │    dsh     │ │ agent │ │
│  │ -adapter   │ │ graph-     │ │ -adapter   │ │ -adapter   │ │ -core │ │
│  │            │ │ adapter    │ │ (进程级)    │ │            │ │ (Rust)│ │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └───┬───┘ │
└────────┼──────────────┼──────────────┼──────────────┼────────────┼─────┘
         ▼              ▼              ▼              ▼            ▼
┌──────────────────────────────────────────────────────────────────────┐
│            运行时集群（每适配器一组 Pod · 独立扩缩容/故障域）             │
│  AgentScope Runtime │ LangGraph 执行器 │ Codex 沙箱进程 │ dsh 插件树    │
│  agent-core 服务（Rust 单二进制）                                    │
└───────────────────────────┬──────────────────────────────────────────┘
                            ▼ 依赖
┌──────────────────────────────────────────────────────────────────────┐
│                    AI 基础设施层（公共 · 建一次）                       │
│  模型网关（多提供商/路由/fallback/预算） │ Vault/KMS 凭证 │ MCP 网关     │
│  PostgreSQL │ Redis │ Milvus/pgvector │ MinIO/S3 │ 沙箱集群(E2B/OCI)  │
│  Prometheus │ Grafana │ Loki │ LangSmith(可选) │ 事件日志存储(审计)     │
└──────────────────────────────────────────────────────────────────────┘
```

### 分层职责

| 层 | 职责 | 是否公共 | 关键约束 |
|---|---|---|---|
| 接入层 | 多端统一接入、认证、渠道适配 | ✅ 建一次 | 只调控制面 API，不感知具体运行时 |
| 控制面 | 租户/资源/发布/审批/审计/计量 | ✅ 建一次 | **框架无关**：不 import 任何框架的运行时 |
| 运行时适配层 | 统一契约 + 各运行时翻译 | ✅ 建一次（每适配器一份） | 端口最小化，差异靠能力矩阵兜底 |
| 运行时集群 | 各框架/自研内核的实际执行 | 🔁 可插拔 | 每适配器一组 Pod，独立故障域 |
| AI 基础设施 | 模型/凭证/存储/沙箱/可观测 | ✅ 建一次 | 全部运行时共享；凭证只进 Vault |

---

## 2. 平台底座（公共层）

### 2.1 接入层与控制面

沿用 `agentscope/技术架构方案.md` 第 1–6 章的设计（租户两级空间、Hub 体系、Agent 配置与发布物化、MCP 网关、渠道适配器）——这些章节**天然框架无关**，原样成为底座公共设计。差异只在第 7 章"运行时层"：从"基于 agentscope.app"改写为"运行时适配层"（见 §3）。

### 2.2 AI 基础设施层（新增公共层）

底座为所有运行时统一供给的 AI 基建：

| 设施 | 设计要点 | 事实依据 / 出处 |
|---|---|---|
| **模型网关** | 多提供商统一 Provider 端口（Anthropic/OpenAI/DeepSeek/Qwen/GLM）+ 路由 + fallback + 成本预算；首事件前重试、流中错误上抛 | agent-core《技术架构方案》§6（现成蓝本） |
| **凭证管理** | 租户级密钥池，密钥只进 Vault/KMS，日志脱敏，凭证不出 MCP 网关 | agentscope 方案 §8 / §11 |
| **MCP 网关** | 协议代理 + 按租户注入凭证 + 高风险写操作审批 + 审计；所有运行时的 MCP 流量必经网关 | agentscope 方案 ADR-004 |
| **沙箱集群** | E2B/Docker/OCI 起步，Linux landlock/seccomp 纵深（agent-core §7.3 为蓝本）；网络 egress 默认拒绝 | 四框架方案 + agent-core §7 |
| **可观测** | 统一审计事件流（各运行时翻译为 `StreamEvent` 写入事件日志存储）、tracing + Prometheus + Loki | dsh"事件日志单一事实源"为参考目标 |
| **数据** | PostgreSQL（控制面）/ Redis（会话/锁）/ Milvus·pgvector（向量）/ MinIO（对象） | 四框架方案共用 |

> **设计原则**：AI 基础设施是**能力供给**而非**运行时一部分**——运行时通过端口向底座声明"我要用什么"，底座按需注入（模型、凭证、沙箱、MCP），运行时永不直接接触密钥与业务库。

---

## 3. 运行时适配层（本架构的核心新增）

### 3.1 运行时端口（Runtime Port）

所有适配器实现同一最小契约（**做薄**：只定各运行时都具备的最小集，差异交给能力矩阵）：

```
trait RuntimePort {
    capabilities() -> CapabilityManifest        // 能力声明：沙箱/审批/checkpoint/多代理…
    create_session(release_id, tenant_ctx) -> Session
    resume_session(session_id) -> Session       // 断点恢复
    submit_input(session_id, input) -> Stream<StreamEvent>  // 归一化事件流
    request_approval(...) -> ApprovalHandle     // 审批挂起（HITL）
    cancel(session_id) -> ()
    materialize(release_snapshot) -> ()         // 运行时无关快照 → 各运行时实体
    translate_isolation(tenant_contract) -> ()  // 平台租户语义 → 各运行时隔离机制
}
```

### 3.2 事件归一化

各运行时事件流统一翻译为 `StreamEvent`：

| StreamEvent | agentscope | langchain-graph | codex | dsh | agent-core |
|---|---|---|---|---|---|
| `TextDelta` | 框架流 | 节点输出 | CLI 输出解析 | `assistant/chunk` | 流式事件 |
| `ToolUse/ToolResult` | 框架工具事件 | 工具节点 | 工具调用记录 | `tool/call·result` | 工具执行事件 |
| `ApprovalRequired` | `DEFAULT` ASK | Checkpointer 中断（HITL） | `require_escalated` | 瀑布拦截 | `Policy` 审批 |
| `Checkpoint` | 框架会话恢复 | Checkpointer 快照 | `state_5.sqlite` 分段 | 事件日志（全量） | 会话持久化 |
| `Error` | LlmError 分类 | 节点异常 | 进程退出码 | `request-error` | 错误分类恢复 |

### 3.3 能力矩阵（差异兜底）

端口之外，各运行时能力差异显著——Agent 发布时由控制面校验"该运行时是否满足此 Agent 能力需求"，不满足则发布期拦截：

| 能力 | agentscope | langchain-graph | codex | dsh | agent-core（自研） |
|---|---|---|---|---|---|
| 执行形态 | Python 框架运行时 | Python 图执行器 | 闭源黑盒（进程级） | TS 插件树 | Rust 单二进制 |
| 多租户原生 | 无（平台四路径） | 无（快照隔离） | 无（进程/工作区隔离） | 作用域隔离 | tenant_id 贯穿 |
| 审批/HITL | `DEFAULT` ASK | Checkpointer 中断 | `require_escalated` | 瀑布拦截插件 | Policy 端口（设计） |
| checkpoint/重放 | 会话恢复 | Checkpointer ✅ | 分段快照 ✅ | 事件日志单一事实源 ✅ | 会话持久化（设计） |
| 沙箱 | local/docker/e2b | 外部注入 | workspace-write ✅ | sandbox 插件 | landlock/seccomp（设计） |
| 多代理 | 框架内 | DeepAgents ✅ | Agents 子代理 | subagent 插件 | s15–17 移植（设计） |
| 可观测性 | Redis 事件流 | LangSmith | history.jsonl | **最强**（事件日志） | tracing |
| 模型绑定 | 多提供商 | 多提供商 | OpenAI 绑定 | 模型无关 | 多提供商（最全） |
| 开源/可控 | 开源 | 开源 | **闭源订阅** | MIT 开源 | **完全自研** |
| 接入成本 | 低（现成扩展点） | 中（适配器开发） | 中（进程编排） | 高（Cordis 学习曲线） | 高（自研开发） |

### 3.4 物化泛化与隔离翻译

- **物化泛化**：`release` 快照保持**运行时无关**（统一格式：Agent 定义 + 工具声明 + 权限档 + 模型引用），`materialize()` 由各适配器解释为运行时实体。`agentscope/技术架构方案.md` §6.2 的物化流程原样保留，仅"物化目标"从写死 AgentScope 改为按适配器路由。
- **隔离翻译**：平台规定统一隔离契约（数据隔离 / 配额 / 审计归属），`translate_isolation()` 由各适配器翻译——AgentScope 走 ADR-003 四路径，codex 走进程/工作区/凭证/配额，自研内核用 tenant_id 贯穿。**隔离策略收敛在适配器内，不散落业务代码。**

---

## 4. 五条路线一览

| 目录 | 技术基座 | 形态 | 接入方式 | 状态 |
|---|---|---|---|---|
| [agentscope/](agentscope/) | AgentScope 2.0 | 企业级多租户 Agent 平台 | 现成扩展点注入（接入成本最低） | 评审稿 |
| [langchain-graph/](langchain-graph/) | LangChain / LangGraph | 图状态机编排平台 | 图定义下发 + Checkpointer 对接 | 评审稿 |
| [codex/](codex/) | OpenAI Codex | 企业级编码 Agent 平台 | 进程级外部编排（闭源黑盒） | 评审稿 |
| [deepseek-harness/](deepseek-harness/) | DeepSeek Harness | Harness 底座（Everything is a Plugin） | 插件树组装 + 事件日志对接 | 评审稿 |
| [../agent-core/](../agent-core/) | **完全自研**（Rust） | 服务端执行引擎 | HTTP/gRPC 直连（最可控） | **设计存档**（暂不开发） |

> 各目录的三件套（技术架构 / 实施计划 / 阶段总览）继续有效——它们是"该运行时如何接入底座"的详细方案；本文档是总纲，只做统一与差异裁决。

---

## 5. 落地路径

```
M0 底座骨架（控制面 + 接入层 + AI 基础设施占位）
  → M1 接第一个适配器：agentscope（现有工作包成适配器，成本≈0，验证端口契约）
  → M2 接第二个适配器：agent-core（自研、最可控，反向验证端口设计是否够薄）
  → M3 能力矩阵 + 发布期能力校验 + 多运行时共存（同一底座同时服务不同 Agent 类型）
  → M4 按需接入 langchain-graph / codex / dsh（业务驱动，不一次性全接）
```

**关键取舍（写进 ADR 候选）**：

1. **端口做薄**：只定最小契约，差异靠能力矩阵兜底——抽象层做厚等于自研运行时（回到 agent-core），做薄则各适配器维护成本可控。
2. **agent-core 优先于商业框架接入**：自研内核最能验证端口设计，且不受上游变更绑架。
3. **底座与各框架文档的关系**：底座文档 = 公共层 + 适配层总纲；框架三件套 = 各适配器实现细节；agent-core 文档 = 自研运行时设计蓝本 + 其自身实施方案。

---

## 6. 约定（框架子目录）

- **每个框架一个子目录**（当前 `agentscope/`、`codex/`、`deepseek-harness/`、`langchain-graph/`；后续引入其他框架时各建一个目录）；
- 每个框架目录内统一三件套：
  - `技术架构方案.md`（建成什么样 + 如何接入底座适配层）
  - `实施计划方案.md`（怎么建）
  - `全流程阶段总览.md`（阶段导航，可选）
- 新增框架时须在 README 目录表登记，并补充其在**能力矩阵**中的一行。

## 7. 目录

| 框架 | 技术基座 | 状态 |
|---|---|---|
| [agentscope/](agentscope/) | AgentScope 2.0（企业级多租户 Agent 平台） | 评审稿 |
| [codex/](codex/) | OpenAI Codex（企业级编码 Agent 平台） | 评审稿 |
| [deepseek-harness/](deepseek-harness/) | DeepSeek Harness（dsh，Everything is a Plugin 的 Harness 底座） | 评审稿 |
| [langchain-graph/](langchain-graph/) | LangChain / LangGraph（图状态机编排平台） | 评审稿 |

## 8. 与其他目录的关系

- 选型依据 ← [../research/](../research/)（研究知识库：产品对比 / 框架全景 / 标准设计）
- 自研运行时 ← [../agent-core/](../agent-core/)（**第五适配器**，唯一自研内核；其技术方案同时是底座"自研运行时蓝本"与"AI 基础设施（模型网关等）蓝本"）
- 技术教学 ← [../tutorials/](../tutorials/)（s01–s20 harness 原理，运行时机制的事实来源）
