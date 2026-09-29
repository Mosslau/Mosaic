# Agent 产品深度对比 · 总览

> **对比对象**：Claude Code（Anthropic）｜Codex（OpenAI）｜DeepSeek Harness（DeepSeek）｜Dify（LangGenius）
> 
> **视角**：定位、能力与 Agent Loop 设计
> 
> **数据来源**：官方文档、deepseek-harness 源码（本环境运行于其上）、Dify 官方资料
>
> **数据快照**：2026-08（Star 15.3 万等数值为该时点 GitHub 值）；**刷新约定**：产品参数（hooks 数、路径、命令）变更时先改本目录 01-04，再检查 [../AgentLoop演进与设计/](../AgentLoop演进与设计/README.md) 与 [../Agent工程范式演进.md](../Agent工程范式演进.md) 的引用
> 
> **配套文档**：方法论见 [`../Agent工程范式演进.md`](../Agent工程范式演进.md)（六层演进栈）、工具选型见 [`../Agent工具与框架合集.md`](../Agent工具与框架合集.md)

---

## 一、四款产品一句话定位

| 产品 | 一句话定位 | 本质 |
|:--|:--|:--|
| **Claude Code** | 终端里的编码 Agent——让 Claude 直接在你的代码库里干活 | 个人级编码工具 |
| **Codex** | OpenAI 的编码 Agent，沙箱安全 + 会话可重放 + Goal 跨会话 | 个人级编码工具（企业化） |
| **DeepSeek Harness (dsh)** | "Everything is a Plugin" 的 Agent Harness——循环本身可替换 | 框架 / 底座 |
| **Dify** | 低代码 Agent 应用平台——工作流 DAG 显式编排 + LLMOps | 企业级平台 |

四个产品覆盖了从"个人工具"到"企业平台"的完整光谱：**工具（CC/Codex）→ 框架（dsh）→ 平台（Dify）**。

## 二、总览对比表

| 维度 | Claude Code | Codex | DeepSeek Harness (dsh) | Dify |
|:--|:--|:--|:--|:--|
| **定位** | 编码 Agent（终端） | 编码 Agent（终端+桌面+IDE） | Agent Harness（框架） | Agent 应用平台（低代码） |
| **形态** | CLI / 桌面 | CLI / 桌面 / IDE | 框架（Web UI / headless / SDK） | Web 平台 / 自托管 |
| **模型绑定** | Claude 系 | OpenAI 系 | **模型无关**（适配器插件） | 多 Provider（数十家） |
| **目标用户** | 个人/资深开发者 | OpenAI 生态开发者 | Harness 深度定制者 | 产品/业务团队 |
| **编排范式** | 隐式自由循环 | 隐式循环 + Goal 跨会话 | 插件化 turn/step 循环 | **显式工作流 DAG** |
| **项目记忆** | CLAUDE.md | AGENTS.md | 插件（context/workspace） | 知识库 + 会话变量 |
| **工具接入** | MCP + 内置 | MCP + 内置 | **一切皆插件**（MCP 插件） | 插件市场 + 工具节点 |
| **沙箱/安全** | 权限匹配 + 审批 | **workspace-write 沙箱** + 网络隔离 | sandbox 插件 + guard | 多租户 + RBAC + 审批 |
| **可观测** | hooks 日志、/status | 会话可重放、checkpoint | **事件日志单一事实源** | LLMOps 全套（日志/评估） |
| **跨会话** | /resume + /schedule | **Goal 系统（token 预算）** | 会话持久化 + resume | 应用级持久对话 |
| **自主循环** | /loop + /schedule | goal + sandbox + parallel | schedule + goal 插件 | 定时触发 + workflow |
| **部署** | 本机 | 本机/云端 | 自托管/嵌入 | 自托管/云 |
| **许可** | 闭源（订阅） | 闭源（订阅） | **MIT 开源** | 开源（社区版 Apache-2.0 带 Dify 例外/企业版） |

## 三、文档导航

| 文件 | 内容 |
|:--|:--|
| [01-ClaudeCode.md](01-ClaudeCode.md) | Claude Code 详细介绍：配置 / Skills / Hooks / 子代理 / 自主循环 / Loop 设计 |
| [02-Codex.md](02-Codex.md) | Codex 详细介绍：沙箱模型 / 工具 / Goal 系统 / 会话重放 / Loop 设计 |
| [03-DeepSeekHarness.md](03-DeepSeekHarness.md) | DeepSeek Harness 详细介绍：插件化架构 / 事件域 / turn-step 生命周期 / Loop 设计 |
| [04-Dify.md](04-Dify.md) | Dify 详细介绍：工作流 / Agent 节点 / RAG / LLMOps / Loop 设计 |
| [05-横向解读与选型.md](05-横向解读与选型.md) | 关键差异解读 + 强度评级 + 选型建议 |
| [../AgentLoop演进与设计/README.md](../AgentLoop演进与设计/README.md) | **Agent Loop 总纲**（AgentLoop 目录入口）：演进机理(01) → 横向对比(02) → 标准设计(03) → 范式与选型 |

**本套文档的重点是 Agent Loop**：[../AgentLoop演进与设计/README.md](../AgentLoop演进与设计/README.md) 目录是核心（演进机理 + 四款对比 + 标准设计），01-04 是素材，05 是选型。

## 四、阅读建议

- 只想选一款**编码工具**：读 01、02，再翻 05 的选型建议
- 想**自建 Agent 底座**：读 03（dsh 是唯一完全开源可定制者），再读 [../AgentLoop演进与设计/03-标准设计.md](../AgentLoop演进与设计/03-标准设计.md)（标准企业 Agent Loop 设计）
- 想**让业务团队搭应用**：读 04（Dify），[../AgentLoop演进与设计/03-标准设计.md](../AgentLoop演进与设计/03-标准设计.md) §5「按团队阶段落地建议」看"平台化"阶段
- 想理解**循环设计本质**：直接读 [../AgentLoop演进与设计/01-演进机理.md](../AgentLoop演进与设计/01-演进机理.md)（演进机理）与 [../AgentLoop演进与设计/02-横向对比.md](../AgentLoop演进与设计/02-横向对比.md)（机制深对比），这是四款产品架构的分水岭
