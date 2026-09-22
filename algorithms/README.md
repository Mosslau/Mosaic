# 算法实验总索引

> 理论总纲：[`../roadmap/人工智能代表算法演进路线.md`](../roadmap/人工智能代表算法演进路线.md)
> 目录按演进阶段分组，编号即学习顺序。
> 原则：**手写核心逻辑（numpy / 纯 Python），禁止调 sklearn/torch 现成算法接口**；数据加载和可视化可以用现成工具。
> 每完成一个实验，把索引表状态从 ⬜ 改为 ✅ 并记录日期。

## 目录组织原则（不设统一模板）

每个算法目录按**自身的类型**设计接口，不套统一模板：

| 算法族 | 示例 | 自然接口 | 对照对象 |
|---|---|---|---|
| 监督估计器 | 线性回归、SVM、决策树 | `Model.fit(X, y)` / `Model.predict(X)` | sklearn 同接口 |
| 搜索求解器 | A*、Minimax、MCTS | `solve(...) -> 解` / `search(state) -> action` | 基线算法（Dijkstra / 随机策略 / 无剪枝版） |
| 深度生成 | GAN、Diffusion、VAE | `Model.train(data)` / `Model.sample()` | PyTorch 对照 |
| 流水线 | RAG | 按链路组织（检索 → 生成） | 端到端指标 |

各目录文件形态随算法而异：可能是 `framework.py`（框架对照），也可能是 `baseline.py`（基线对照），
也可能只有 `impl.py` + `demo.py`（对照在 impl 内部，如 minimax 的剪枝对比）。
仓库级唯一约定：每个算法目录保留 `README.md`（导航 + 状态），索引表在此维护。

**手写 vs 对照原则**：每个实验必须同时跑手写版和对照版（框架或基线），对比指标与耗时，
分析差异原因——手写理解原理，对照理解工程。

## 01-search · 符号主义与搜索

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [A* 启发式搜索](01-search/a-star/) | 2.2.1 | ✅ | 2026-09-14 |
| [Minimax 与 Alpha-Beta 剪枝](01-search/minimax-alphabeta/) | 2.2.1 | ⬜ | |
| [蒙特卡洛树搜索 MCTS](01-search/mcts/) | 2.2.1 | ⬜ | |

## 02-statistical-ml · 统计机器学习

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [线性回归与梯度下降](02-statistical-ml/linear-regression/) | 3.2.1 | ⬜ | |
| [逻辑回归](02-statistical-ml/logistic-regression/) | 3.2.1 | ⬜ | |
| [支持向量机 SVM](02-statistical-ml/svm/) | 3.2.2 | ⬜ | |
| [决策树 ID3/CART](02-statistical-ml/decision-tree/) | 3.2.3 | ⬜ | |
| [随机森林](02-statistical-ml/random-forest/) | 3.3.1 | ⬜ | |
| [K-Means 聚类](02-statistical-ml/kmeans/) | 3.4.1 | ⬜ | |
| [PCA 主成分分析](02-statistical-ml/pca/) | 3.4.2 | ⬜ | |
| [朴素贝叶斯](02-statistical-ml/naive-bayes/) | 3.5 | ⬜ | |

## 03-deep-learning · 深度学习

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [感知机](03-deep-learning/perceptron/) | 4.2 | ⬜ | |
| [MLP 与手写反向传播](03-deep-learning/mlp-backprop/) | 4.2 | ⬜ | |
| [卷积神经网络 LeNet](03-deep-learning/cnn-lenet/) | 4.3.1 | ⬜ | |
| [RNN 与 LSTM](03-deep-learning/rnn-lstm/) | 4.4 | ⬜ | |
| [自编码器 AutoEncoder](03-deep-learning/autoencoder/) | 4.5 | ⬜ | |
| [生成对抗网络 GAN](03-deep-learning/gan/) | 4.6 | ⬜ | |

## 04-transformer · Transformer 时代

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [注意力机制](04-transformer/attention/) | 5.2 | ⬜ | |
| [迷你 Transformer Block](04-transformer/mini-transformer/) | 5.1 | ⬜ | |
| [迷你 GPT 字符级语言模型](04-transformer/mini-gpt/) | 5.3.4 | ⬜ | |

## 05-generative · 生成式 AI

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [变分自编码器 VAE](05-generative/vae/) | 4.5 | ⬜ | |
| [迷你扩散模型 DDPM](05-generative/mini-diffusion/) | 6.3 | ⬜ | |
| [迷你 RAG 检索增强生成](05-generative/mini-rag/) | 8.1 | ⬜ | |

## 推荐起步顺序（前 5 个）

1. [线性回归与梯度下降](02-statistical-ml/linear-regression/) —— 一切优化的起点
2. [感知机](03-deep-learning/perceptron/) → [MLP 手写反向传播](03-deep-learning/mlp-backprop/) —— 深度学习的 Hello World
3. [决策树 ID3/CART](02-statistical-ml/decision-tree/) —— 理解"划分"思想，集成学习的地基
4. [A* 启发式搜索](01-search/a-star/) —— 符号主义代表，呼应 Agent 规划
5. [K-Means 聚类](02-statistical-ml/kmeans/) —— 无监督入门
