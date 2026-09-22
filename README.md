# 💧 MindSpring

> **心智之泉，溯智能之源头**
> 
> *Where intelligence springs from.*

**A laboratory for AI core technologies.**

从机器学习基础到深度学习前沿，亲手实现智能的每一层源头——神经网络、训练框架与推理引擎。

## 当前阶段：梳理 / 规划（未进入实现）

本仓库**刚开始**，目前处于「梳理阶段」——先把方向、路线、契约与骨架定下来，再逐个开工。如实说明现状，避免误读：

| 线 | 已经就位 | 尚未开始 |
|---|---|---|
| `roadmap/` | 领域技术路线（2,154 行）+ 职业路线（1,198 行）✅ | — |
| `algorithms/` | 索引 23 个实验 + 章节锚点 + 1 个样板实验（a-star ✅，含 15 项测试） | 其余 22 个实验 |
| `engineering/` | 七阶段项目清单 + **6 份项目定义**（六段式，含可勾选验收清单） | 6 个系统的实现（其中 06-agent-nest 处于 Part 1 沉淀） |
| 契约 | `mindspring-lab` skill（手写纪律 / 双跑对照 / 章节锚定 / 六段模板）+ 自动校验脚本 | CI 与测试体系（实现阶段补） |

因此：**这里的目录是"待做清单"而不是"已完成产物"**。骨架与验收标准先行，是本仓库刻意的做法——先想清楚"什么算做完"，再动手。

## 与 TenetLang 的分工

同一工作区下的 [TenetLang](../TenetLang/) 承载**语言学习与工程纪律的语义层**（如 AI 平台控制面的任务/配额/模型/发布语义、湖仓与编排的口径语义，已实跑验证）；MindSpring 承载**真实系统的实现与真实指标**（真调度、真推理、真压测、真成本）。**TenetLang 讲"应该怎么做、为什么"，MindSpring 交付"跑起来的系统与实测数字"——两者不重复。**

## Why "MindSpring"?
A spring is where water is born — pure and ever-flowing. So is the 
source of intelligence. This project traces AI back to its origin, 
one experiment at a time.

## Structure

```
MindSpring/
├── algorithms/    动手：算法原理实验（手写 numpy vs 框架对照）
├── engineering/   动手：工程系统实战（对应职业路线七阶段）
└── roadmap/       动脑：领域技术路线 + 个人职业路线
```

| 目录 | 内容 |
|---|---|
| [algorithms/](algorithms/) | 按演进路线逐章手写实现经典算法，与 sklearn/PyTorch 对照验证 |
| [engineering/](engineering/) | 语料流水线、RAG 知识库、GPU 调度、推理服务、Agent 平台等可运行系统 |
| [roadmap/](roadmap/) | AI 算法演进综述 + 大模型数据中心平台工程师成长路径 |
