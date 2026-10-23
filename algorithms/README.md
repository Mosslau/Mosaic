# 算法实验总索引

> 理论总纲：[`./docs/人工智能代表算法演进路线.md`](./docs/人工智能代表算法演进路线.md)
> 目录按演进阶段分组，编号即学习顺序；族目录用 **`p` + 两位编号**（`p01-search` … `p05-generative`），实验目录用 kebab-case 算法名。
> 原则：**手写核心逻辑（numpy / 纯 Python），禁止调 sklearn/torch 现成算法接口**；数据加载和可视化可以用现成工具。
> 每完成一个实验，把索引表状态从 ⬜ 改为 ✅ 并记录日期。
> 阶段成熟度评估（2026-10-22）：[阶段成熟度评估-2026-10-22.md](阶段成熟度评估-2026-10-22.md)

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

## 运行环境（uv）

本目录用 [uv](https://docs.astral.sh/uv/) 管理 Python 与依赖：依赖声明在 [`pyproject.toml`](pyproject.toml)，
解释器版本锁在 [`.python-version`](.python-version)（3.13），精确版本锁在 [`uv.lock`](uv.lock)。
`.venv/` 由 uv 生成、不入库（见仓库根 `.gitignore`）。

```bash
cd algorithms
uv sync --extra dev                          # 首次：建 .venv，装 numpy / matplotlib / scikit-learn + pytest / ruff
uv run python p01-search/a-star/demo.py      # 在项目环境里跑，无需 activate
uv run pytest p01-search/a-star/ -q
```

各实验 README 的命令一律带 `uv run` 前缀；在 `algorithms/` 或该实验目录下执行均可
（uv 会向上找到 `algorithms/pyproject.toml`）。历史验证记录里保留的 `python3` / `.venv/bin/python`
是当时的复现痕迹，不代表现在的推荐用法。

**度量口径**：各实验的耗时数字都是「本机某次运行」的观测值，随机器、Python/matplotlib 版本浮动——
只用于同机、同次对比（节点数、胜率、代价这类确定性指标才可跨机复现）。

## p01-search · 符号主义与搜索

> 族内学习顺序：无信息搜索 → A* → Minimax/Alpha-Beta → MCTS → CFR → CSP。
> 前四个解决「在一张图（或博弈树）上找」，CFR 把「看不到对手的牌」补上，
> CSP 则换了问题形态：「没有图，只有一堆约束」。
> 每份 README 的「局限与延伸」都写明了它指向的下一个实验（族内双向链接）。
> 族级导读（六个实验各解决什么问题、彼此什么关系、该读哪个）：[p01-search/README.md](p01-search/README.md)。

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [无信息搜索 DFS/BFS/UCS](p01-search/uninformed-search/) | 2.2.1 | ✅ | 2026-10-09 |
| [A* 启发式搜索](p01-search/a-star/) | 2.2.1 | ✅ | 2026-09-14 |
| [Minimax 与 Alpha-Beta 剪枝](p01-search/minimax-alphabeta/) | 2.2.1 | ✅ | 2026-10-09 |
| [蒙特卡洛树搜索 MCTS](p01-search/mcts/) | 2.2.1 | ✅ | 2026-10-09 |
| [反事实遗憾最小化 CFR](p01-search/cfr/) | 2.2.1 | ✅ | 2026-10-09 |
| [约束满足问题 CSP](p01-search/csp/) | 2.2.2 | ✅ | 2026-10-09 |

## p02-statistical-ml · 统计机器学习

> 族内学习顺序：线性回归 → 逻辑回归 → 正则化与模型选择 → SVM → 决策树 → 随机森林
> → Boosting/GBDT → K-Means → PCA → 朴素贝叶斯 → 异常检测。
> 前六个建立「损失 / 分类 / 划分 / 集成」的主线，正则化补上「泛化」，
> Boosting 补齐集成里 bagging 之外的另一半，最后三个走向无监督与概率视角。
> 族级导读（11 个实验什么关系、该读哪个）：[p02-statistical-ml/README.md](p02-statistical-ml/README.md)。

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [线性回归与梯度下降](p02-statistical-ml/linear-regression/) | 3.2.1 | ✅ | 2026-10-21 |
| [逻辑回归](p02-statistical-ml/logistic-regression/) | 3.2.1 | ✅ | 2026-10-21 |
| [正则化与模型选择](p02-statistical-ml/regularization/) | 3.2.1 | ✅ | 2026-10-21 |
| [支持向量机 SVM](p02-statistical-ml/svm/) | 3.2.2 | ✅ | 2026-10-21 |
| [决策树 ID3/CART](p02-statistical-ml/decision-tree/) | 3.2.3 | ✅ | 2026-10-21 |
| [随机森林](p02-statistical-ml/random-forest/) | 3.3.1 | ✅ | 2026-10-21 |
| [Boosting 与 GBDT](p02-statistical-ml/boosting/) | 3.3.2 | ✅ | 2026-10-21 |
| [K-Means 聚类](p02-statistical-ml/kmeans/) | 3.4.1 | ✅ | 2026-10-21 |
| [PCA 主成分分析](p02-statistical-ml/pca/) | 3.4.2 | ✅ | 2026-10-21 |
| [朴素贝叶斯](p02-statistical-ml/naive-bayes/) | 3.5 | ✅ | 2026-10-21 |
| [异常检测](p02-statistical-ml/anomaly-detection/) | 3.9 | ✅ | 2026-10-21 |

## p03-deep-learning · 深度学习

> 族内学习顺序：感知机 → MLP/反向传播 → CNN → RNN/LSTM → AutoEncoder → GAN。
> 前两个建立「可学习非线性 + 反向传播」的主线，CNN/RNN 补上空间与时间结构，
> AutoEncoder/GAN 走向无监督表示与生成。
> 与 p02 的对照：人工特征 → 表示学习；与 p04 的接力：RNN → 注意力。
> 族级导读（6 个实验什么关系、该读哪个、开工前的补强计划）：[p03-deep-learning/README.md](p03-deep-learning/README.md)。
> 阶段横向对照与质量项：[/p03-deep-learning/stage_benchmark.py](p03-deep-learning/stage_benchmark.py)。

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [感知机](p03-deep-learning/perceptron/) | 4.2 | ✅ | 2026-10-22 |
| [MLP 与手写反向传播](p03-deep-learning/mlp-backprop/) | 4.2 | ✅ | 2026-10-22 |
| [卷积神经网络 LeNet](p03-deep-learning/cnn-lenet/) | 4.3.1 | ✅ | 2026-10-22 |
| [RNN 与 LSTM](p03-deep-learning/rnn-lstm/) | 4.4 | ✅ | 2026-10-22 |
| [自编码器 AutoEncoder](p03-deep-learning/autoencoder/) | 4.5 | ✅ | 2026-10-22 |
| [生成对抗网络 GAN](p03-deep-learning/gan/) | 4.6 | ✅ | 2026-10-22 |

## p04-transformer · Transformer 时代

> 族内学习顺序：注意力机制 → 迷你 Transformer Block → BERT → 迷你 GPT → T5。
> 先做“组件”（attention），再做“可堆叠 Block”，然后换 mask/目标得到三种范式：
> BERT（双向 encoder）、GPT（因果 decoder）、T5（encoder-decoder + cross-attention）。
> 不先手写 attention 直接写 GPT，等于把最难的反传藏在黑盒里。
> 族级导读（5 个实验什么关系、接口边界、数据/范围/Phase 0–5 计划）：[p04-transformer/README.md](p04-transformer/README.md)。
> 阶段横向对照与完成度：[stage_benchmark.py](p04-transformer/stage_benchmark.py)。

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [注意力机制](p04-transformer/attention/) | 5.2 | ✅ | 2026-10-22 |
| [迷你 Transformer Block](p04-transformer/mini-transformer/) | 5.2 | ✅ | 2026-10-22 |
| [BERT / 掩码语言模型](p04-transformer/bert/) | 5.3.2 | ✅ | 2026-10-22 |
| [迷你 GPT 字符级语言模型](p04-transformer/mini-gpt/) | 5.3.4 | ✅ | 2026-10-22 |
| [T5 / 编码器-解码器](p04-transformer/t5/) | 5.3.3 | ✅ | 2026-10-22 |

## p05-generative · 生成式 AI

> 族内学习顺序：VAE → DDPM（含条件生成/CFG 子实验）→ RAG。
> VAE 是概率 latent，DDPM 是去噪生成，RAG 是检索增强的生成应用；
> DDPM 的条件生成/CFG 作为该实验的子实验，不单开第 4 个目录。
> 族级导读：[p05-generative/README.md](p05-generative/README.md)。

| 实验 | 章节 | 状态 | 完成日期 |
|---|---|---|---|
| [变分自编码器 VAE](p05-generative/vae/) | 4.5 | ✅ | 2026-10-23 |
| [迷你扩散模型 DDPM](p05-generative/mini-diffusion/) | 6.3 | ⬜ | |
| [迷你 RAG 检索增强生成](p05-generative/mini-rag/) | 8.1 | ⬜ | |

## 推荐起步顺序（前 5 个）

1. [线性回归与梯度下降](p02-statistical-ml/linear-regression/) —— 一切优化的起点
2. [感知机](p03-deep-learning/perceptron/) → [MLP 手写反向传播](p03-deep-learning/mlp-backprop/) —— 深度学习的 Hello World
3. [决策树 ID3/CART](p02-statistical-ml/decision-tree/) —— 理解"划分"思想，集成学习的地基
4. [A* 启发式搜索](p01-search/a-star/) —— 符号主义代表，呼应 Agent 规划
5. [K-Means 聚类](p02-statistical-ml/kmeans/) —— 无监督入门
