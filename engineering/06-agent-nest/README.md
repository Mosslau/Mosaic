# agent-nest（Agent 工程平台）

> 状态：🚧 进行中
> 对应 roadmap 阶段：第 六 阶段
> 对应文档：`roadmap/大模型数据中心平台工程师.md`

## 目标

**终极目标**：统一平台底座（接入 / 控制面 / AI 基础设施建一次）+ 可插拔运行时（四框架 + 自研内核按能力矩阵接入），让 Agent 从"孵化"到"归巢"全程有底座可依。

一句话可检验：同一底座上，至少两个运行时（框架适配器 + 自研 agent-core）通过同一 Runtime Port 契约完成 Agent 的发布与运行。

## 技术栈

| 层 | 技术基线 |
|---|---|
| 平台底座（公共层） | PostgreSQL / Redis / Milvus·pgvector / MinIO·S3 / Vault·KMS / Prometheus·Grafana·Loki / E2B·OCI 沙箱（设计基线，详见 [frameworks/](frameworks/)） |
| 运行时适配（四框架） | AgentScope 2.0、LangChain / LangGraph、OpenAI Codex（进程级编排）、DeepSeek Harness（TS 插件树） |
| 自研内核 agent-core | Rust + tokio，单二进制，HTTP/gRPC 直连 |
| 教学轨道 tutorials | Python 3（单文件 `code.py`）+ Rust（Cargo workspace），s01–s20 双轨道对齐 |

## 系统架构

```
        一个平台底座（接入层 / 控制面 / AI 基础设施，只建一次）
              │ 只依赖运行时端口
              ▼
   运行时适配层（Runtime Port & Adapter，统一契约 + 能力矩阵兜底）
   ┌──────────┬──────────┬──────────┬──────────┬───────────┐
   │ agentscope│ langchain│  codex   │   dsh    │ agent-core│
   │ -adapter │ -graph   │ -adapter │ -adapter │ -adapter  │
   │          │ -adapter │ (闭源)   │          │ (自研Rust)│
   └──────────┴──────────┴──────────┴──────────┴───────────┘
```

- 控制面**框架无关**：不 import 任何框架的运行时；发布物化为运行时无关快照，由各适配器翻译
- 端口做薄：只定各运行时最小契约（会话生命周期 / StreamEvent 事件流 / 审批挂起 / 隔离翻译），差异靠能力矩阵在发布期校验
- 完整架构总纲与能力矩阵见 [frameworks/README.md](frameworks/README.md)

## 目录导航

| 子目录 | 角色 | 状态 |
|---|---|---|
| [research/](research/) | 研究知识库：方法论、演进机理、产品对比、框架全景、工具收藏 | 基本完备 |
| [tutorials/](tutorials/) | 从零手写 Agent Harness 教学（Python + Rust 双轨道，s01–s20） | 已完结 |
| [frameworks/](frameworks/) | 统一平台底座总纲 + 四框架三件套（技术架构 / 实施计划 / 阶段总览） | 评审稿 |
| [agent-core/](agent-core/) | 自研核心：完全自研运行时，底座的第五适配器 | 设计存档（暂不开发） |

## 复用的算法实验

无直接代码复用——本项目当前处于 Part 1（知识与方案沉淀），尚未进入编码阶段。原理层面的关联（供 Part 2 编码时回访）：

- [../../algorithms/04-transformer/attention/](../../algorithms/04-transformer/attention/)：Agent 智能来源（模型侧）的注意力机制原理
- [../../algorithms/05-generative/mini-rag/](../../algorithms/05-generative/mini-rag/)：检索增强生成的最小闭环，对应 Agent 的知识 / 记忆供给
- [../../algorithms/01-search/mcts/](../../algorithms/01-search/mcts/)：搜索与规划思想，对应 Agent 的规划（todo）与任务分解机制

## 验收标准

Part 1（沉淀）：

- [x] research 方法论（六层演进 / 产品对比 / 框架全景）沉淀完备
- [x] tutorials 双轨道教学（Python + Rust，s01–s20）完结
- [x] frameworks 四框架三件套 + agent-core 设计存档齐备（评审稿）
- [ ] 方案评审定稿，选定 Part 2 首个落地对象（A 门禁）

Part 2（实证）：

- [ ] 能跑通 agent-core 的 mock-LLM 最小闭环主循环（B-1，不依赖任何框架，独立验证循环设计）
- [ ] agentscope 适配器真接 RuntimePort：发布物化 / 事件流 / 审批挂起 / 隔离翻译，M0 门禁全过（B-2）

Part 3（规模化）：

- [ ] 同一底座同时服务 ≥2 种运行时（langchain-graph / codex / dsh 按需接入），能力矩阵多行点亮
- [ ] AI 基础设施（模型网关 / Vault / MCP 网关 / 沙箱 / 可观测）只建一次，全部运行时共享
- [ ] 多运行时共存 + 发布期能力校验 + 统一可观测审计

## 演进路线

```
Part 1（沉淀）──门禁──▶ Part 2（实证）──门禁──▶ Part 3（规模化）
知识库/方案库          单一落地验证              多运行时 + AI 基础设施
        🔄 当前所处          ⏳ 未开始                  ⏳ 终极目标
```

**下一步（当前唯一阻塞点）**：执行 A 门禁——方案评审定稿，选定 Part 2 首个落地对象（候选：agent-core mock-LLM 最小闭环 / agentscope 适配器）。

## 实施笔记

- **2026-08 架构收敛**：`frameworks/` 四条框架路线与 `agent-core/` 自研路线原共享 80% 公共建设（接入 / 控制面 / AI 基础设施），分别建设 = 重复造轮子；收敛为"一个底座 + 可插拔运行时"，agent-core 从并列路线降级为第五适配器
- **关键取舍一：端口做薄**——Runtime Port 只定最小契约，差异靠能力矩阵兜底；抽象层做厚等于自研运行时（回到 agent-core），做薄则各适配器维护成本可控
- **关键取舍二：agent-core 优先于商业框架接入**——自研内核最能验证端口设计是否够薄，且不受上游变更绑架
- **关键取舍三：agent-core 设计存档暂不开发**（2026-08-27）——先归档设计，待 Part 2 评审后决定；其《技术架构方案》同时作为底座"自研运行时蓝本"与"AI 基础设施蓝本"
- **门禁节奏**：Part 1 → 2 → 3 各有明确门禁，不过门禁不进入下一阶段，避免底座未实证就铺开多运行时
