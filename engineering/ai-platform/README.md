# Engineering — 工程系统实战

> 对应文档：[`../../roadmap/大模型数据中心平台工程师.md`](../../roadmap/大模型数据中心平台工程师.md)
> 定位：把职业路线里的实战项目一个个做出来。与 `algorithms/`（学原理）不同，这里做**可运行的完整系统**。

> **当前阶段：梳理 / 规划（未进入实现）**——七阶段项目清单与六份项目定义（六段式 + 可勾选验收清单）已就位；六个系统尚未开工，`06-agent-nest` 处于 Part 1（知识沉淀，未进入编码）。本目录当前是**待做清单**，不是已完成产物。

## 与 algorithms/ 的区别

| | `algorithms/` | `engineering/ai-platform/` |
|---|---|---|
| 目标 | 搞懂单个算法的原理 | 串起完整系统的链路 |
| 粒度 | 一个目录一个算法 | 一个目录一个可运行系统 |
| 产出 | 笔记 + 手写 vs 框架对比实验 | 可部署的服务 / 平台 Demo |
| 评价标准 | 指标与框架对齐 | 达到验收标准、能跑通端到端 |

## 项目总览（对应 roadmap 七个学习阶段）

| 阶段 | 项目 | 验收标准一句话 | 状态 | 完成日期 |
|---|---|---|---|---|
| 一 | [01-text-corpus-pipeline](01-text-corpus-pipeline/) | 10GB 文本清洗 + 去重 + embedding 流水线跑通 | ⬜ | |
| 二 | [02-rag-knowledge-base](02-rag-knowledge-base/) | 企业知识库问答系统，检索 + 生成 + 引用溯源 | ⬜ | |
| 三 | [03-lakehouse-vector](03-lakehouse-vector/) | 向量化数据湖，Iceberg/Delta + 向量索引统一管理 | ⬜ | |
| 四 | [04-gpu-scheduler-demo](04-gpu-scheduler-demo/) | K8s GPU 调度平台 Demo，能提交/监控训练任务 | ⬜ | |
| 五 | [05-inference-server](05-inference-server/) | OpenAI 兼容推理服务，压测出 TTFT/TPOT/tokens/s | ⬜ | |
| 六 | [06-agent-nest](06-agent-nest/) | Agent 平台底座 + 可插拔运行时（四框架 + 自研内核），端口契约被至少一个运行时实证 | 🚧 | |
| 七 | [07-ai-platform](07-ai-platform/) | 端到端整合：数据接入 → 清洗 → RAG → 微调 → 调度 → 推理 → Agent 托管 → 监控 → 成本统计 | ⬜ | |

## 依赖关系与开工顺序

每个系统的**项目定义**（各自 README 的六段）已给出「复用的算法实验」；下表把依赖收成一张图。开工顺序建议：**先纵切两端（01 数据入口 + 05 推理出口）**，再补中间（03 存储版本、02 检索），最后做受硬件约束的 04 与集成层 07。

| 阶段 | 项目 | 前置算法实验（`algorithms/`） | 前置项目 | 受什么约束 |
|---|---|---|---|---|
| 一 | 01-text-corpus-pipeline | `05-generative/mini-rag`（向量化口径）、`02-statistical-ml/kmeans`、`02-statistical-ml/pca`；**去重算法需新增手写实验** | — | 数据规模（10GB 需流式/Spark） |
| 二 | 02-rag-knowledge-base | `05-generative/mini-rag`（内核）、`04-transformer/attention`（Rerank 原理）、`kmeans`、`pca` | 01（语料与向量） | 向量库与 LLM 外部依赖 |
| 三 | 03-lakehouse-vector | `mini-rag`（索引口径）、`kmeans`（布局/聚簇）、`pca`（压缩分析） | 01 | 表格式与对象存储 |
| 四 | 04-gpu-scheduler-demo | 无直接复用（基础设施编排）；`01-search/a-star` 的"可解释评估"思想可类比 | — | **真实 GPU + K8s（最大约束）** |
| 五 | 05-inference-server | `04-transformer/mini-gpt`、`mini-transformer`、`attention`（prefill/decode 与 KV Cache） | 04（算力与部署）可选 | GPU / 量化工具链 |
| 六 | 06-agent-nest | 自身在 Part 1 沉淀，编码期再回访相关实验 | 02/05（作为工具与模型来源） | 沙箱与运行时依赖 |
| 七 | 07-ai-platform | 集成层：复用前六个项目，不直接依赖单个算法实验 | 一~六全部 | 单机资源（Compose 起步） |

> 交叉约束：**04 是唯一受硬件门槛限制的项目**（无 GPU 时只能做逻辑层验证，其 README 已把验收拆成"逻辑层/真实层"两层）；**07 可增量推进**（骨架先行，每完成一个阶段接入一个组件），因此不必等前面全部完成。

## 与 languages/ 的边界

languages/ 承载**语言与工程纪律的语义层**（AI 平台控制面的任务/配额/模型/发布语义、湖仓与编排的口径语义，已实跑验证），本项目做**真实系统与真实指标**（真调度、真推理、真压测、真成本）。同一个概念（例如"GPU 资源账本的不变量"或"幂等回填的下游闭包"）在两处的分工是：**languages/ 讲清"应该怎么做、为什么"，engineering/ai-platform/ 交付"跑起来的系统与实测数字"**——写项目定义时先查 languages/ 是否已覆盖语义，避免重复造文档。

