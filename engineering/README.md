# engineering —— 工程系统部分

Mosaic 的第 ③ 部分。两个**并列**域：把「AI 平台」与「数据平台」做成真实可运行的系统，与 `algorithms/`（学原理）不同，这里交付**跑起来的系统与实测数字**。

| 域 | 目录 | 内容 | 规模 |
|---|---|---|---|
| AI 平台 | `ai-platform/` | 语料流水线、RAG 知识库、湖仓+向量、GPU 调度、推理服务、Agent 平台、端到端整合 | 7 个项目 |
| 数据平台 | `data-platform/` | Go 接入网关与编解码、Kafka/Flink SQL 流处理、ClickHouse 服务层、Compose 部署与门禁 | 1 套系统 |

## ai-platform 的依赖关系与开工顺序

每个项目的**项目定义**（各自 README 的六段）已给出「复用的算法实验」；开工顺序建议：**先纵切两端（01 数据入口 + 05 推理出口）**，再补中间（03 存储版本、02 检索），最后做受硬件约束的 04 与集成层 07。

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

## 与 languages/ 的分工

[`languages/`](../languages/) 承载**语言学习与工程纪律的语义层**（如 AI 平台控制面的任务/配额/模型/发布语义、湖仓与编排的口径语义，已实跑验证）；本域承载**真实系统的实现与真实指标**（真调度、真推理、真压测、真成本）。**languages/ 讲"应该怎么做、为什么"，engineering/ 交付"跑起来的系统与实测数字"——两者不重复。**

## 校验

```bash
python3 .dsh/skills/mindspring-lab/scripts/validate.py
cd ../engineering/data-platform && bash scripts/check-docs.sh
```
