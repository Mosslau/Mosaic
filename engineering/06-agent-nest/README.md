# 🪺 AgentNest

> **智能之巢，育千机与万灵**
> 
> *Where agents are born, raised, and set free.*

**A framework for building & orchestrating AI Agents.**

智能体的孵化之地——工具调用、记忆管理、多 Agent 协作，在此筑巢成生态。

## Why "AgentNest"?

A nest is where life hatches and grows. Each agent starts as an egg 
(a simple prompt), learns to fly (tools & memory), and finally joins 
the flock (multi-agent collaboration).

## Docs

研究知识：

- 方法论、演进机理、产品对比、框架全景、工具收藏 [research/README.md](research/README.md)

系统配套：

- 从零教学 [tutorials/](tutorials/) 
- 统一平台底座（接入 / 控制面 / AI 基础设施 + 可插拔运行时适配层：四框架 + 自研）[frameworks/](frameworks/)
- 自研核心（完全自研运行时，底座的第五适配器）[agent-core/](agent-core/)

## 🎯 终极目标与演进路线

**终极目标**：统一平台底座（接入 / 控制面 / AI 基础设施建一次）+ 可插拔运行时（四框架 + 自研内核按能力矩阵接入），让 Agent 从"孵化"到"归巢"全程有底座可依。

```
Part 1（沉淀）──门禁──▶ Part 2（实证）──门禁──▶ Part 3（规模化）
知识库/方案库          单一落地验证              多运行时 + AI 基础设施
        🔄 当前所处          ⏳ 未开始                  ⏳ 终极目标
```

### Part 1：知识库 / 方案库（沉淀）— 🔄 进行中

| 内容 | 状态 |
|---|---|
| research 方法论（六层演进 / 产品对比 / 框架全景） | ✅ 基本完备 |
| tutorials 双轨道教学（Python + Rust，s01–s20） | ✅ 已完结 |
| frameworks 四框架三件套 + agent-core 设计存档 | ✅ 已齐（评审稿） |
| 门禁：方案评审定稿 + 选定 Part 2 落地对象 | ⏳ 待办 |

### Part 2：单一落地实证（验证）— ⏳ 未开始

- B-1 最小闭环：agent-core 的 mock-LLM 主循环——独立验证"循环设计对不对"（不依赖任何框架）
- B-2 端口契约：agentscope 适配器真接 RuntimePort——发布物化 / 事件流 / 审批挂起 / 隔离翻译，M0 门禁全过
- 门禁：端口契约被至少一个运行时实证，能力矩阵第一行点亮，具备接入第二个运行时的能力

### Part 3：多运行时规模化（终极目标）— ⏳ 未开始

- 同一底座同时服务多种 Agent 类型：接 langchain-graph / codex / dsh，能力矩阵多行点亮
- AI 基础设施（模型网关 / Vault / MCP 网关 / 沙箱 / 可观测）只建一次，全部运行时共享
- 门禁：多运行时共存 + 发布期能力校验 + 统一可观测审计

**下一步（当前唯一阻塞点）**：执行 A 门禁——方案评审定稿，选定 B 阶段首个落地对象（候选：agent-core mock-LLM 最小闭环 / agentscope 适配器）。
