# Engineering — 工程系统实战

> 对应文档：[`../roadmap/大模型数据中心平台工程师.md`](../roadmap/大模型数据中心平台工程师.md)
> 定位：把职业路线里的实战项目一个个做出来。与 `algorithms/`（学原理）不同，这里做**可运行的完整系统**。

## 与 algorithms/ 的区别

| | `algorithms/` | `engineering/` |
|---|---|---|
| 目标 | 搞懂单个算法的原理 | 串起完整系统的链路 |
| 粒度 | 一个目录一个算法 | 一个目录一个可运行系统 |
| 产出 | 笔记 + 手写 vs 框架对比实验 | 可部署的服务 / 平台 Demo |
| 评价标准 | 指标与框架对齐 | 达到验收标准、能跑通端到端 |

## 项目总览（对应 roadmap 六个学习阶段）

| 阶段 | 项目 | 验收标准一句话 | 状态 |
|---|---|---|---|
| 一 | [01-text-corpus-pipeline](01-text-corpus-pipeline/) | 10GB 文本清洗 + 去重 + embedding 流水线跑通 | ⬜ |
| 二 | [02-rag-knowledge-base](02-rag-knowledge-base/) | 企业知识库问答系统，检索 + 生成 + 引用溯源 | ⬜ |
| 三 | [03-lakehouse-vector](03-lakehouse-vector/) | 向量化数据湖，Iceberg/Delta + 向量索引统一管理 | ⬜ |
| 四 | [04-gpu-scheduler-demo](04-gpu-scheduler-demo/) | K8s GPU 调度平台 Demo，能提交/监控训练任务 | ⬜ |
| 五 | [05-inference-server](05-inference-server/) | OpenAI 兼容推理服务，压测出 TTFT/TPOT/tokens/s | ⬜ |
| 六 | [06-ai-platform](06-ai-platform/) | 端到端整合：数据接入 → 清洗 → RAG → 微调 → 调度 → 推理 → 监控 | ⬜ |
