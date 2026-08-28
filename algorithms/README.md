# 算法实验总索引

> 对应文档：`../../docs/人工智能代表算法演进路线.md`
> 原则：**手写核心逻辑（numpy），禁止调 sklearn/torch 现成算法接口**；数据加载和可视化可以用现成工具。
> 新实验从 `TEMPLATE/` 复制，每个实验完成后把状态从 ⬜ 改为 ✅ 并记录日期。

## 实验统一结构

```
algorithm-name/
├── README.md      # 设计原理 → 数学推导 → 手写要点 → 框架对照 → 实验结果 → 局限与延伸
├── impl.py        # numpy 手写实现
├── framework.py   # sklearn / PyTorch 框架对照调用
└── demo.py        # 同数据双跑：手写 vs 框架，指标并排对比 + 可视化
```

**双跑原则**：每个实验必须同时跑手写版和框架版，对比指标与耗时，分析差异原因——手写理解原理，框架理解工程。

## 进度总览

| 阶段 | 实验 | 状态 | 完成日期 |
|---|---|---|---|
| 01 符号主义：搜索 | [A* 启发式搜索](01-search/a-star/) | ⬜ | |
| | [Minimax 与 Alpha-Beta 剪枝](01-search/minimax-alphabeta/) | ⬜ | |
| | [蒙特卡洛树搜索 MCTS](01-search/mcts/) | ⬜ | |
| 02 统计机器学习 | [线性回归与梯度下降](02-statistical-ml/linear-regression/) | ⬜ | |
| | [逻辑回归](02-statistical-ml/logistic-regression/) | ⬜ | |
| | [支持向量机 SVM](02-statistical-ml/svm/) | ⬜ | |
| | [决策树 ID3/CART](02-statistical-ml/decision-tree/) | ⬜ | |
| | [随机森林](02-statistical-ml/random-forest/) | ⬜ | |
| | [K-Means 聚类](02-statistical-ml/kmeans/) | ⬜ | |
| | [PCA 主成分分析](02-statistical-ml/pca/) | ⬜ | |
| | [朴素贝叶斯](02-statistical-ml/naive-bayes/) | ⬜ | |
| 03 深度学习 | [感知机](03-deep-learning/perceptron/) | ⬜ | |
| | [MLP 与手写反向传播](03-deep-learning/mlp-backprop/) | ⬜ | |
| | [卷积神经网络 LeNet](03-deep-learning/cnn-lenet/) | ⬜ | |
| | [RNN 与 LSTM](03-deep-learning/rnn-lstm/) | ⬜ | |
| | [自编码器 AutoEncoder](03-deep-learning/autoencoder/) | ⬜ | |
| | [生成对抗网络 GAN](03-deep-learning/gan/) | ⬜ | |
| 04 Transformer 时代 | [注意力机制](04-transformer/attention/) | ⬜ | |
| | [迷你 Transformer Block](04-transformer/mini-transformer/) | ⬜ | |
| | [迷你 GPT 字符级语言模型](04-transformer/mini-gpt/) | ⬜ | |
| 05 生成式 AI | [变分自编码器 VAE](05-generative/vae/) | ⬜ | |
| | [迷你扩散模型 DDPM](05-generative/mini-diffusion/) | ⬜ | |
| | [迷你 RAG 检索增强生成](05-generative/mini-rag/) | ⬜ | |

## 推荐起步顺序（前 5 个）

1. **线性回归与梯度下降** —— 一切优化的起点
2. **感知机 → MLP 手写反向传播** —— 深度学习的 Hello World
3. **决策树 ID3/CART** —— 理解"划分"思想，集成学习的地基
4. **A\* 启发式搜索** —— 符号主义代表，呼应 Agent 规划
5. **K-Means 聚类** —— 无监督入门
