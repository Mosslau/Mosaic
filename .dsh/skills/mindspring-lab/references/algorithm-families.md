# 算法族接口约定

> 新增实验（场景 A 第 2 步）先查本表确定：文件形态、自然接口、对照对象。
> 原则：**每个算法目录按自身的类型设计接口，不套统一代码模板**——本 skill 统一的是 README 结构与实验纪律，不是代码形态。

## 四族总表

| 算法族 | 典型算法 | 自然接口 | 对照版文件 | 对照对象 |
|---|---|---|---|---|
| 监督估计器 | 线性回归、逻辑回归、SVM、决策树、随机森林、K-Means、PCA、朴素贝叶斯 | `Model.fit(X, y)` / `Model.predict(X)` | `framework.py` | sklearn 同接口 |
| 搜索求解器 | A*、Minimax、MCTS | `solve(problem) -> 解` / `search(state) -> action` | `baseline.py` | 基线算法（Dijkstra / 无剪枝版 / 随机策略） |
| 深度模型 | 感知机、MLP、LeNet、RNN/LSTM、AutoEncoder、GAN、Attention、mini-GPT、VAE、Diffusion | `Model.train(data)` / `Model.sample()` 或前向/反向手写 | `framework.py` | PyTorch 对照 |
| 流水线 | mini-RAG | 按链路组织（检索 → 生成） | 内嵌于 `demo.py` | 端到端指标 |

## 文件形态的自由度

- 三件套（`impl.py` + 对照 + `demo.py`）是常见形态，不是强制形态
- 对照逻辑可以内嵌：如 minimax 的"有剪枝 vs 无剪枝"对比直接在 `impl.py`/`demo.py` 内部做，不需要单独 `baseline.py`
- 流水线族可以没有单一 `Model` 接口，按链路模块组织
- 允许README 加「目录形态」段（文件 × 角色 × 接口表格）说明本实验的实际形态

## 手写纪律的界限（按族细化）

| 族 | impl.py 允许 | impl.py 禁止 |
|---|---|---|
| 监督估计器 | numpy 矩阵运算、手写梯度 | `sklearn.*` 估计器、`scipy.optimize` 现成求解器 |
| 搜索求解器 | 纯 Python 数据结构（heapq 等） | 现成图算法库（networkx 的 A* 等） |
| 深度模型 | `torch.Tensor`、`torch.autograd`（张量与求导是工具） | `torch.nn.*` 现成层、`torch.optim.*` 现成优化器、`torchvision.models` |
| 流水线 | 各环节中已完成的算法实验代码 | 直接调 LangChain 等框架的现成链 |

灰度判断：问自己"这一行调用的东西是不是本实验要理解的原理本身"——是，就必须手写；只是工具（求导、绘图、数据加载、评估指标）就可用库。

## 对照版本的选择逻辑

- **有同名框架接口**（sklearn/PyTorch 一行能调的）→ 框架对照，重点分析"框架多做了什么"（向量化、正则化、数值稳定性、并行）
- **没有现成框架接口**（搜索类）→ 基线对照，重点量化"本算法相对朴素基线的收益"（如 A* vs Dijkstra 的扩展节点数）
- **端到端系统**（RAG）→ 指标对照，消融实验（去掉某环节看指标掉多少）
