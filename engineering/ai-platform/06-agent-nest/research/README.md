# AgentNest 文档体系 · 总入口

> **一句话主线**：从 Prompt Engineering 走向 Loop Engineering——ReAct 用"提示词"制造循环，现代 Agent Loop 用"运行时"制造循环，并被 Graph Engineering 接棒。
>
> 本目录是 AgentNest 的研究知识库：方法论 → 演进机理 → 产品对比 → 框架全景 → 工具收藏，五条线支撑 [../frameworks/](../frameworks/) 的落地与 [../tutorials/](../tutorials/) 的教学。

## 文档地图（5 个入口）

| 入口 | 角色 | 内容 | 适合谁 |
|:--|:--|:--|:--|
| [Agent工程范式演进.md](Agent工程范式演进.md) | 方法论 | 六层演进栈（Prompt→Context→Harness→Loop→Graph→Eco） | 想建立全局认知 |
| [AgentLoop演进与设计/](AgentLoop演进与设计/README.md) | 演进机理 + 标准设计 | 14 维演进图谱 / 四款对比 / 企业级标准设计（可落地产物） | 想理解循环本质 / 照着搭 |
| [Agent产品对比/](Agent产品对比/README.md) | 产品事实源 | Claude Code / Codex / dsh / Dify 四款深挖 + 评级选型 | 选编码工具 / 底座 |
| [Agent主流开发框架/](Agent主流开发框架/README.md) | 框架全景 | 32 个框架分类 + 选型速查 + 趋势观察 | 选框架 / 平台 |
| [Agent工具与框架合集.md](Agent工具与框架合集.md) | 工具收藏 | 69 仓库 Star 主表 + 行动优先级 | 挑工具 / 技能 |

## 推荐阅读顺序

1. **10 分钟建立全貌**：读 [Agent工程范式演进.md](Agent工程范式演进.md)（六层栈）
2. **理解循环**：读 [AgentLoop演进与设计/README.md](AgentLoop演进与设计/README.md) → 01-演进机理（14 维）→ 02-横向对比（四款）→ 03-标准设计（落地）
3. **选型落地**：读 [Agent产品对比/README.md](Agent产品对比/README.md)（工具/底座）→ [Agent主流开发框架/06-选型速查.md](Agent主流开发框架/06-选型速查.md)（框架/平台）
4. **按需查表**：[Agent工具与框架合集.md](Agent工具与框架合集.md)（Star 主表）、[Agent主流开发框架/07-趋势观察.md](Agent主流开发框架/07-趋势观察.md)（2026 趋势）

## 数据与维护约定

- **Star 数据权威点**：[合集主表](Agent工具与框架合集.md)（收藏项目）+ [框架 README 主表](Agent主流开发框架/README.md)（非收藏项目）；框架/01-05 速览表与产品对比/04 的星值**以主表为准**，刷新时同步。
- **产品事实权威点**：[Agent产品对比/](Agent产品对比/README.md)（01-04 单篇）；其余文档引用其结论，变更时先改此处再检查 [AgentLoop演进与设计/](AgentLoop演进与设计/README.md) 与 [Agent工程范式演进.md](Agent工程范式演进.md) 的引用。
- **选型结论权威点**：[Agent主流开发框架/06-选型速查.md](Agent主流开发框架/06-选型速查.md)（框架级）+ [Agent产品对比/05-横向解读与选型.md](Agent产品对比/05-横向解读与选型.md)（产品级）；各入口互链、不重复全文。
- **时效**：各文档头部标注撰写/快照时点（2026-08 起）；具体实现细节（事件名/工具名/参数名）以标注时点的源码/文档为准。

## 配套仓库

- [../tutorials/](../tutorials/)：从零手写 harness 的教学代码（python / rust，s01-s20 与本目录概念一一对应）
- [../frameworks/](../frameworks/)：统一平台底座（接入 / 控制面 / AI 基础设施 + 可插拔运行时适配层：agentscope / langchain-graph / codex / dsh / 自研 agent-core）——本文档为选型与设计依据

## 维护说明

- 新增专题文档：放入对应目录，并在此地图登记；长文（>100 行）加目录。
- 改文件名/章节号：同步本地图与全库引用（重命名后跑一次死链检查）。
