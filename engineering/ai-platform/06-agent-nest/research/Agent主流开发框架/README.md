# 主流 Agent 开发框架汇总 · 总览

> 按「国内 / 海外」两大阵营整理，热度以 GitHub Stars 及月下载量为参考。

---

## 一、分类框架

| 阵营 | 类别 | 数量 | 这一类是干什么的 |
|:--|:--|:--:|:--|
| 国内 | **代码级框架** | 7 | 可直接写代码集成的 Agent 框架 |
| 国内 | **平台 / 低代码** | 6 | 可视化/零代码搭 Agent 应用 |
| 海外 | **通用编排框架** | 11 | 多 Agent 编排 / 工作流的事实标准 |
| 海外 | **现象级项目** | 3 | 现象级热度项目（2025-2026 新秀 + 2023 鼻祖） |
| 海外 | **TS 阵营 & 平台** | 5 | TypeScript 生态与可视化平台 |

**共 32 行 / 约 38 个项目**（组合行：LangChain+LangGraph、Flowise+SuperAGI、百炼/ADP/千帆），覆盖"代码级 → 平台级"完整光谱。

## 二、全部框架一览

| 框架 | 阵营 | 类别 | 热度 | 一句话定位 |
|:--|:--|:--|:--|:--|
| MetaGPT | 国内 | 代码级 | ⭐ 7.0万 | 多智能体模拟软件公司 |
| DeerFlow | 国内 | 代码级 | ⭐ 8.1万 | 字节 SuperAgent harness，/goal 自主执行 |
| AgentScope | 国内 | 代码级 | ⭐ 3.0万 | 阿里 AOP 智能体，Python/TS/Java |
| Qwen-Agent | 国内 | 代码级 | ⭐ 1.7万 | 通义官方 ReAct + 工具调用 |
| DB-GPT | 国内 | 代码级 | ⭐ 2.0万 | 数据智能体，Text2SQL |
| OpenManus | 国内 | 代码级 | ⭐ 639 | Manus 开源复刻，通用自治 |
| Spring AI Alibaba | 国内 | 代码级 | ⭐ 1.1万 | Java/Spring 的 AI 应用框架 |
| Dify | 国内 | 平台 | ⭐ 15.3万 | LLM 应用/Agent 平台，RAG + 工作流 + 私有化 |
| Coze 扣子 | 国内 | 平台 | ⭐ 2.2万 | 零代码 Bot，一键发布飞书/微信/抖音 |
| FastGPT | 国内 | 平台 | ⭐ 2.9万 | 知识库问答专精，部署轻 |
| RAGFlow | 国内 | 平台 | ⭐ 8.9万 | 深度文档解析 RAG |
| MaxKB | 国内 | 平台 | ⭐ 2.3万 | 开源知识库问答，客服场景 |
| 百炼 / ADP / 千帆 | 国内 | 平台 | 闭源 | 大厂企业级 Agent 平台 |
| LangChain / LangGraph | 海外 | 编排 | ⭐ 14.5万/4.0万 | 图状态机编排，生产级事实标准 |
| DeepAgents | 海外 | 编排 | ⭐ 2.8万 | LangChain 官方多 Agent harness，基于 LangGraph（batteries-included） |
| CrewAI | 海外 | 编排 | ⭐ 5.8万 | 角色驱动多 Agent，上手最快 |
| AutoGen | 海外 | 编排 | ⭐ 6.1万 | 对话式多 Agent 鼻祖（转维护） |
| Microsoft Agent Framework | 海外 | 编排 | ⭐ 1.3万 | AutoGen + SK 合并继任 |
| OpenAI Agents SDK | 海外 | 编排 | ⭐ 2.9万 | 轻量 Handoff 机制 |
| Google ADK | 海外 | 编排 | ⭐ 2.1万 | 层级 Agent 树，原生多模态 |
| Claude Agent SDK | 海外 | 编排 | ⭐ 0.8万 | Claude 生态，安全护栏 |
| LlamaIndex | 海外 | 编排 | ⭐ 5.2万 | RAG / 文档密集型 |
| Pydantic AI | 海外 | 编排 | ⭐ 1.9万 | 类型安全，FastAPI 风格 |
| smolagents | 海外 | 编排 | ⭐ 2.9万 | 极简 Code Agent（约千行） |
| Hermes Agent | 海外 | 现象级 | ⭐ 23.6万 | 四层记忆 + 闭环自我进化 |
| OpenClaw | 海外 | 现象级 | ⭐ 38.8万 | 本地优先电脑操控 |
| AutoGPT | 海外 | 现象级 | ⭐ 18.7万 | 自主 Agent 鼻祖 |
| n8n | 海外 | TS | ⭐ 20.2万 | 工作流自动化 + AI 节点 |
| LangFlow | 海外 | TS | ⭐ 15.4万 | 可视化拖拽编排 |
| Mastra | 海外 | TS | ⭐ 2.7万 | TS 全栈 Agent 框架 |
| Vercel AI SDK | 海外 | TS | ⭐ 2.6万 | 流式 UI + 工具调用标准 |
| Flowise / SuperAGI | 海外 | TS | ⭐ 5.5万 / 1.8万 | 可视化链路 / GUI 自主 Agent |

## 三、文档导航

| 文件 | 内容 |
|:--|:--|
| [01-国内代码级框架.md](01-国内代码级框架.md) | MetaGPT / DeerFlow / AgentScope / Qwen-Agent / DB-GPT / OpenManus / Spring AI Alibaba 详解 |
| [02-国内平台与低代码.md](02-国内平台与低代码.md) | Dify / Coze / FastGPT / RAGFlow / MaxKB / 大厂平台 详解 |
| [03-海外通用编排框架.md](03-海外通用编排框架.md) | LangChain/LangGraph / DeepAgents / CrewAI / AutoGen / 微软 / OpenAI / Google / Claude / LlamaIndex / Pydantic / smolagents 详解 |
| [04-海外现象级项目.md](04-海外现象级项目.md) | Hermes Agent / OpenClaw / AutoGPT 详解 |
| [05-海外TS阵营与平台.md](05-海外TS阵营与平台.md) | n8n / LangFlow / Mastra / Vercel AI SDK / Flowise / SuperAGI 详解 |
| [06-选型速查.md](06-选型速查.md) | 8 条选型规则 + 许可协议 + 决策矩阵 |
| [07-趋势观察.md](07-趋势观察.md) | 2026 五大趋势详解 |

## 四、阅读建议

- **只要选一个框架**：读 06（选型速查）就够了
- **国内私有化部署**：读 01、02
- **海外生产级编排**：读 03，配合 [`Agent产品对比/`](../Agent产品对比/README.md) 的四款产品深对比
- **追热点**：读 04、07
