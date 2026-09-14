# Agent 工具与框架合集（GitHub Stars）

> 来源：https://github.com/stars/Mosslau/lists/llm
> 
> 数据截至：2026-08-25｜共 **69** 个仓库，Star 合计约 **501 万**（2026-08-25 按 GitHub API 全量复核：69/69 一致；表中 Star 展示为四舍五入的近似值）
> 
> **刷新方式**：Star 为手动快照——刷新时用 GitHub API（`https://api.github.com/repos/<owner>/<repo>`）核对主表 Star 列，只改主表一处；stars 列表（`github.com/stars/Mosslau/lists/llm`）有新增时整体重刷并更新分类/优先级。

## 一、总览与分类框架

69 个仓库按 **三层核心 + 外围支撑** 分 6 类，共 44 核心 + 25 外围：

| 层 | 分类 | 数量 | 这一类是干什么的 | 代表 |
| :--- | :--- | ---: | :--- | :--- |
| 方法论 | **Skills 技能库** | 14 | 把人类经验与工作流封装为 AI 可加载的技能模块 | superpowers、anthropics/skills、spec-kit |
| 编排 | **Harness 扩展** | 6 | 给 agent 加能力外壳：hooks / 命令 / 插件 / 沙箱 | ECC、deepseek-harness |
| 编排 | **Multi-Agent** | 14 | 多 agent 协同：角色分工 / 并行 / 流水线 | claw-code、deer-flow、crewAI、DB-GPT |
| 基础设施 | **Token/智能** | 10 | 用更少 token 获得更精准上下文（压缩 + 索引） | rtk、caveman、codegraph |
| 外围 | **工具与生态** | 13 | 即装即用的 MCP / CLI / 桌面工具 | chrome-devtools-mcp、pi |
| 外围 | **学习资源** | 12 | 教程 / 课程 / 专著 | learn-claude-code、ai-agent-book |

**优先级分布**：✅ 已在使用 3｜🔥 立即采用 14｜🧪 值得测试 14｜👀 关注观望 28｜⏸️ 暂不需要 10

**对本仓库的三个结论**：

1. **Skills 方法论**提升文档质量——doc-coauthoring、spec-kit 的 SDD 闭环、superpowers 的 brainstorming/writing-plans 可直接用于文档产线；
2. **多 Agent 编排**支撑智能电动车平台的多语言栈分工协作——crewAI 三角色 crew、openai-agents-python 嵌入 Python AI 应用层、claw-code 作长期主力储备；
3. **Token 优化工具**降低使用成本——rtk 压 CLI 输入、caveman 压回复输出、OmniRoute 在网关层叠加路由+压缩。

---

## 二、仓库主表（全部 69 个项目的分类 + 定位）

> 行动优先级语义：🔥 立即采用（本周就做）→ 🧪 值得测试（评估后决定）→ 👀 关注观望（跟踪进展）→ ⏸️ 暂不需要（当前用不上）→ ✅ 已在使用。

| 仓库 | 分类 | 优先级 | Stars | 一句话定位 |
| :--- | :--- | :--- | ---: | :--- |
| [obra/superpowers](https://github.com/obra/superpowers) | Skills | 🔥 | 277K | Agentic Skills 框架 + 软件开发方法论，Star 最高 |
| [anthropics/skills](https://github.com/anthropics/skills) | Skills | 🔥 | 171K | Anthropic 官方 Agent Skills 仓库（含 doc-coauthoring） |
| [github/spec-kit](https://github.com/github/spec-kit) | Skills | 🔥 | 131K | GitHub 官方 SDD 工具包：spec→plan→implement→validate |
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | Skills | 🔥 | 25K | Agent Skills 正式规范标准，Anthropic 贡献开源 |
| [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) | Skills | 🧪 | 66K | spec-kit 轻量替代 |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | Skills | 👀 | 207K | Karpathy LLM 编码缺陷总结 |
| [garrytan/gstack](https://github.com/garrytan/gstack) | Skills | 👀 | 130K | 角色化工作流方法论，Think→Plan→Build→Ship |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Skills | 👀 | 90K | 生产级 skills 参考 |
| [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) | Skills | 👀 | 65K | 轻量 SDD+上下文工程 |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | Skills | 👀 | 30K | skills 分发安装端 |
| [vercel-labs/skills](https://github.com/vercel-labs/skills) | Skills | 👀 | 30K | npx 一键安装，35+ agent |
| [garrytan/gbrain](https://github.com/garrytan/gbrain) | Skills | 👀 | 29K | Garry Tan 的 Agent Brain，知识图谱+混合检索 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | Skills | ⏸️ | 236K | 偏前端，栈不匹配 |
| [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills) | Skills | ⏸️ | 11K | 全栈开发技能，不匹配 |
| [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) | Harness | 🧪 | 194K | DeepSeek 官方插件化 harness，Everything is a Plugin |
| [mindfold-ai/Trellis](https://github.com/mindfold-ai/Trellis) | Harness | 🧪 | 14K | 规格驱动 harness，spec/task/memory 持久化到仓库 |
| [QoderAI/better-harness](https://github.com/QoderAI/better-harness) | Harness | 🧪 | 2.0K | harness 工作循环分析，把会话证据转为改进建议 |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | Harness | 👀 | 243K | 体量大臃肿，观望 |
| [coleam00/Archon](https://github.com/coleam00/Archon) | Harness | 👀 | 23K | harness builder，确定性执行 |
| [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) | Harness | 👀 | 16K | 开放 harness 概念参考 |
| [ultraworkers/claw-code](https://github.com/ultraworkers/claw-code) | Multi-Agent | 🔥 | 195K | 多 Agent 框架，Rust 性能底座，长期主力 |
| [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | Multi-Agent | 🔥 | 81K | 字节开源 SuperAgent harness，长期任务自主执行 |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | Multi-Agent | 🔥 | 58K | Python 角色编排框架，crew/task/process 模型 |
| [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | Multi-Agent | 🔥 | 39K | 5 种编排模式，API 简洁，入门首选 |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | Multi-Agent | 🔥 | 29K | OpenAI 官方多 Agent 框架，handoff + sandbox |
| [fengshao1227/ccg-workflow](https://github.com/fengshao1227/ccg-workflow) | Multi-Agent | 🔥 | 5.8K | 多模型互补协作(Go)，栈高度匹配 |
| [ruvnet/ruflo](https://github.com/ruvnet/ruflo) | Multi-Agent | 🧪 | 69K | swarm 智能+自适应记忆，动态角色分配 |
| [different-ai/openwork](https://github.com/different-ai/openwork) | Multi-Agent | 🧪 | 23K | Claude Cowork 开源替代，跨 agent 共享 skills/MCP 工作流 |
| [snarktank/ralph](https://github.com/snarktank/ralph) | Multi-Agent | 🧪 | 22K | 自主循环 agent，文档自迭代生成 |
| [lobehub/lobehub](https://github.com/lobehub/lobehub) | Multi-Agent | 👀 | 82K | Chief Agent Operator，7×24 agent 编队运营 |
| [aaif-goose/goose](https://github.com/aaif-goose/goose) | Multi-Agent | 👀 | 53K | Linux Foundation 通用 Agent，Rust + 70+ MCP 扩展 |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | Multi-Agent | ⏸️ | 148K | 角色化 agent 过度设计 |
| [jnMetaCode/agency-agents-zh](https://github.com/jnMetaCode/agency-agents-zh) | Multi-Agent | ⏸️ | 20K | agency-agents 中文化 |
| [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph) | Token/智能 | ✅ | 68K | 代码知识图谱，已在使用 |
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Token/智能 | 🔥 | 101K | Caveman-speak 风格压缩输出 token 65%，6 级压缩 |
| [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | Token/智能 | 🔥 | 77K | CLI 输出透明代理压缩，减 60-90% token |
| [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute) | Token/智能 | 🔥 | 55K | 免费 AI 网关，1 endpoint→350+ 提供商自动 fallback |
| [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | Token/智能 | 🧪 | 68K | 通用文本压缩：日志/API 响应/RAG chunk/代码 diff |
| [microsoft/graphrag](https://github.com/microsoft/graphrag) | Token/智能 | 🧪 | 36K | 微软知识图谱 RAG，LLM 提取结构化知识增强推理 |
| [TencentCloud/TencentDB-Agent-Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) | Token/智能 | 🧪 | 24K | 团队级 agent 记忆中心，多 agent 共享记忆服务器 |
| [Egonex-AI/Understand-Anything](https://github.com/Egonex-AI/Understand-Anything) | Token/智能 | 👀 | 80K | 代码→知识图谱，后期评估 |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Token/智能 | 👀 | 41K | 多语言大仓代码智能 |
| [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | Token/智能 | ⏸️ | 92K | 跨会话记忆，暂不需要 |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | 工具与生态 | ✅ | 34K | 官方插件目录 |
| [jarrodwatts/claude-hud](https://github.com/jarrodwatts/claude-hud) | 工具与生态 | ✅ | 28K | 状态栏，已启用 |
| [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | 工具与生态 | 🔥 | 50K | Chrome 官方 MCP，50+ 工具让 agent 操控浏览器 |
| [earendil-works/pi](https://github.com/earendil-works/pi) | 工具与生态 | 🧪 | 97K | 统一 LLM API + agent loop + TUI + coding agent CLI |
| [langchain-ai/openwiki](https://github.com/langchain-ai/openwiki) | 工具与生态 | 🧪 | 16K | LangChain 官方 CLI，自动生成/维护 agent 文档 |
| [f/prompts.chat](https://github.com/f/prompts.chat) | 工具与生态 | 👀 | 168K | 提示词灵感参考源 |
| [usestrix/strix](https://github.com/usestrix/strix) | 工具与生态 | 👀 | 58K | 开源 AI 渗透测试，多 Agent 红队协作 + PoC 验证 |
| [CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit) | 工具与生态 | 👀 | 37K | 前端 Agent UI 栈，生成式 UI 框架 |
| [esengine/DeepSeek-Reasonix](https://github.com/esengine/DeepSeek-Reasonix) | 工具与生态 | 👀 | 35K | DeepSeek 原生 coding agent，Go 实现 prefix-cache 稳定 |
| [herdrdev/herdr](https://github.com/herdrdev/herdr) | 工具与生态 | 👀 | 32K | Rust agent 终端多路复用器，tmux 式分屏管理 |
| [eosphoros-ai/DB-GPT](https://github.com/eosphoros-ai/DB-GPT) | Multi-Agent | 👀 | 20K | 开源 agentic 数据助手，SQL/BI 智能体 |
| [andrewyng/openworker](https://github.com/andrewyng/openworker) | 工具与生态 | 👀 | 15K | Andrew Ng 开源 AI coworker 桌面应用 |
| [microsoft/markitdown](https://github.com/microsoft/markitdown) | 工具与生态 | ⏸️ | 176K | 无外部文档转换需求 |
| [farion1231/cc-switch](https://github.com/farion1231/cc-switch) | 工具与生态 | ⏸️ | 129K | 桌面 GUI，CLI 用不上 |
| [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | 学习资源 | 🧪 | 75K | 从零构建类 Claude Code 的 nano harness 教程 |
| [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | 学习资源 | 🧪 | 65K | vibe coding→agentic engineering 演进方法论 |
| [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | 学习资源 | 👀 | 134K | 100+ AI Agent & RAG 可运行应用合集 |
| [datawhalechina/hello-agents](https://github.com/datawhalechina/hello-agents) | 学习资源 | 👀 | 75K | 中文智能体教程 |
| [microsoft/AI-For-Beginners](https://github.com/microsoft/AI-For-Beginners) | 学习资源 | 👀 | 67K | 微软官方 12 周 24 课 AI 入门课程 |
| [rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch) | 学习资源 | 👀 | 49K | 435 节 AI 工程课 |
| [bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book) | 学习资源 | 👀 | 42K | 《深入理解 AI Agent》中文专著开源仓库 |
| [luongnv89/claude-howto](https://github.com/luongnv89/claude-howto) | 学习资源 | 👀 | 41K | Claude Code 可视化指南+模板 |
| [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor) | 学习资源 | 👀 | 37K | 港大终身个性化辅导 agent，教育场景参考 |
| [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) | 学习资源 | ⏸️ | 64K | 各厂商 system prompt 泄露合集，反向工程参考 |
| [adongwanai/AgentGuide](https://github.com/adongwanai/AgentGuide) | 学习资源 | ⏸️ | 8.7K | AI Agent 求职导向教程（面试题+简历+8-15 周路线） |
| [mengjian-github/openclaw101](https://github.com/mengjian-github/openclaw101) | 学习资源 | ⏸️ | 3.0K | 非当前技术栈 |

---

## 三、分类解读：每一类怎么理解、怎么选

### 1. Skills 技能库（14）— 方法论层
把隐性经验显性化为 AI 可执行的指令模板。**选型顺序**：先立规范（agentskills 标准、anthropics/skills 官方实现）→ 再学方法论（superpowers、spec-kit SDD、gstack 角色化、get-shit-done 上下文工程）→ 最后解决分发（vercel-labs/skills）；karpathy-skills、addyosmani/agent-skills 作为编写范本参考。

### 2. Harness 扩展（6）— 编排层
在编码工具外罩一层能力外壳。**三种路线**：插件化精简（deepseek-harness）、全能重型（ECC，体量过大仅借鉴理念）、规格驱动与仓库持久化（Trellis）；better-harness 做工作循环分析，Archon/OpenHarness 为设计参考。

### 3. Multi-Agent 编排（14）— 编排层
让多个 agent 分工协作。**怎么选**：Python 生态最成熟（crewAI、openai-agents-python）→ 高性能 Rust 底座（claw-code，长期主力）→ 长时域自主 harness（deer-flow）→ 编排模式实验（oh-my-claudecode 5 模式）→ 工作流跨 agent 共享（openwork）；ruflo/ralph 为进阶能力储备。

### 4. Token 优化与代码智能（10）— 基础设施层
两条互补路径：**压缩**解决"太多"（rtk 压 CLI 输出、caveman 压回复、headroom 通用压缩、OmniRoute 网关路由+压缩），**索引**解决"太泛"（codegraph 实时索引、Understand-Anything 全景图、graphrag 知识图谱）；记忆类（claude-mem 单机、TencentDB-Agent-Memory 团队级）。

### 5. 工具与生态（13）— 外围支撑
即装即用：浏览器操控（chrome-devtools-mcp）、统一 API/TUI（pi）、桌面 coworker（openworker）、文档转换（markitdown）、安全测试（strix）、终端多路复用（herdr）、提示词参考（prompts.chat）。

### 6. 学习资源（12）— 外围支撑
从零构建 harness（learn-claude-code）→ 中文专著（ai-agent-book）→ 入门课程（AI-For-Beginners、hello-agents）→ 进阶路线（claude-code-best-practice、ai-engineering-from-scratch）→ 参考合集（awesome-llm-apps、system_prompts_leaks）。

---

## 四、行动优先级

### ✅ 已在使用（3）
codegraph、claude-hud、claude-plugins-official

### 🔥 立即采用（14）

| 仓库 | 行动 | 验收 |
| :--- | :--- | :--- |
| **anthropics/skills** | 安装 doc-coauthoring | 1 篇文档完成协作闭环 |
| **superpowers** | 测 brainstorming + writing-plans | 输出笔记到 research/ |
| **spec-kit** | 1 个新文档走 spec→plan→implement→validate | 产出可复用 SDD 模板 |
| **rtk** | CLI 全量经 rtk 代理 | `rtk gain` 观察一周，验证 60-90% 降低 |
| **caveman** | `npx caveman` 安装，`/caveman` 切换 full 模式 | 输出 token 节省 >50%，配合 rtk 实现双向压缩 |
| **agentskills** | 阅读 agentskills.io 正式规范 | 编写新 skill 时遵循标准格式，确保跨平台兼容 |
| **oh-my-claudecode** | 安装并实验 5 种编排模式（串行/并行/投票/辩论/流水线） | 一周内跑通全部模式，输出对比笔记 |
| **ccg-workflow** | `go install` 编译，用 `/ccg:go` 触发多模型协作 | 验证 Go 栈多模型互补效果 |
| **claw-code** | 关注 Releases 页，API 稳定后立即安装试用 | 作为长期多 Agent 主力框架储备 |
| **deer-flow** | Docker 部署，`/goal` 命令测试长期任务自主执行 | 验证长时域 SuperAgent 模式对智能电动车平台的适用性 |
| **openai-agents-python** | `pip install openai-agents`，构建 Python AI 应用层多 Agent 原型 | 完成一个 handoff + sandbox 的 demo |
| **chrome-devtools-mcp** | `claude mcp add chrome-devtools` 注册 MCP 工具 | 让 agent 能操控浏览器做前端调试和截图验证 |
| **crewAI** | `pip install crewai`，定义 3 角色 crew（研究者/写作者/审校者）跑通文档协作闭环 | 验证角色编排 vs oh-my-claudecode 5 模式的差异，输出对比笔记 |
| **OmniRoute** | 部署网关，将 Claude Code base_url 指向其 endpoint | 观察自动 fallback 与压缩叠加效果，对比 `rtk gain` 成本数据 |

### 🧪 值得测试（14）

| 仓库 | 行动 | 验收 |
| :--- | :--- | :--- |
| **headroom** | 与 rtk 对比压缩效果 | 压缩率 >50% 且信息不丢失 |
| **OpenSpec** | 作 spec-kit 轻量替代测试 | 文档仓库场景比 spec-kit 更轻 |
| **claude-code-best-practice** | 提炼 vibe→agentic 演进路径，输出笔记到 research/ | 与 AgentNest 学习路线互补 |
| **learn-claude-code** | 通读理解 harness 原理 | 输出结构化笔记 |
| **ruflo** | 阅读 swarm+自适应记忆的实现文档 | 输出 swarm 机制笔记，评估引入时机 |
| **ralph** | 编写文档自迭代 prompt 原型（不装框架） | 对一篇长文档完成"起草→对比→修改"闭环 |
| **graphrag** | `pip install graphrag` 安装，小数据集测试索引 | 验证知识图谱 RAG 对跨文档推理的提升效果 |
| **openwiki** | `npm install -g openwiki`，自动维护 CLAUDE.md/AGENTS.md | 代码结构文档自动更新，减少手动同步成本 |
| **pi** | 阅读其 monorepo 架构设计，不安装 | 作为 agent 工具链模块化设计的架构参考 |
| **Trellis** | `npm install -g @mindfoldhq/trellis`，走通四阶段闭环 | 验证 spec→task→memory 仓库持久化对文档质量的作用 |
| **deepseek-harness** | 阅读 "Everything is a Plugin" 插件机制 | 输出插件化 harness 设计笔记（对照本环境 DSH 与 CLAUDE.md 配置） |
| **openwork** | 接入 OpenWork MCP，发布 1-2 个自定义 capability | 验证 skills/MCP 工作流跨 Claude Code/Codex 复用 |
| **TencentDB-Agent-Memory** | Docker 启动 memory-core + hub + proxy 三服务 | 验证多 agent 共享记忆，与 claude-mem 对比评估 |
| **better-harness** | 在 Claude Code 跑一次工作循环分析 | 输出基于会话证据的改进建议，评估是否周期性接入 |

### 👀 关注观望（28）
ECC / gstack / gbrain / Understand-Anything / awesome-llm-apps / lobehub / goose / strix / DeepSeek-Reasonix / herdr / andrej-karpathy-skills / prompts.chat / get-shit-done / addyosmani/agent-skills / hello-agents / claude-howto / ai-engineering-from-scratch / vercel-labs 两个 / Archon / OpenHarness / codebase-memory-mcp / ai-agent-book / AI-For-Beginners / DeepTutor / openworker / CopilotKit / DB-GPT —— 关注进展，评估匹配度。

### ⏸️ 暂不需要（10）
markitdown、mattpocock/skills、agency-agents、agency-agents-zh、cc-switch、claude-mem、claude-skills、openclaw101、AgentGuide、system_prompts_leaks —— 当前场景用不上。
