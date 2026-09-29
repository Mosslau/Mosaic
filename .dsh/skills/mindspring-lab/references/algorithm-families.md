# 算法族接口约定

> 新增实验（场景 A 第 2 步）先查本表确定：文件形态、自然接口、对照对象。
> 原则：**每个算法目录按自身的类型设计接口，不套统一代码模板**——本 skill 统一的是 README 结构与实验纪律，不是代码形态。
> 注：算法族是**接口分类**（决定文件形态与对照对象），族目录（p01-search 等）是**演进阶段分组**（决定学习顺序）；两者维度不同，不必一一对应——如 mini-RAG 属流水线族，但按演进路线放在 `p05-generative/`。

## 四件先定的事（动手写代码前）

**接口只有一个推导来源：「这个算法吃什么、吐什么」。** 按顺序问自己：

1. **有没有独立的 y？** 有 → 监督估计器 `fit(X, y)`；没有（目标是 X 自己或标签要自己造）→ 无监督估计器 `fit(X)`。
   K-Means / PCA / AutoEncoder / VAE / Diffusion / GAN 都属后者，**它们的 `fit(X, y)` 签名本身就是错的**。
2. **输出是"预测"还是"生成"？** 判别式 → `predict`；生成式 → `sample` / `generate`。
   语言模型这类"输入与目标来自同一段数据错位切分"的，用 `train(data)` / `generate(prompt)`——没有独立 y。
3. **它是不是一个可独立训练的模型？** 若只是上层模型的组件（如 attention），就是**模块形态**：
   `forward(...) / backward(...)`，**不要硬造 fit/predict**。
4. **是不是一条链路？** 按环节组织（如 RAG 的 检索 → 生成），不强行收敛到单一 `Model` 接口。

判据一句话：**接口应该让人一眼看出这个算法在做什么**。若某个目录的签名可以原样复制到另一个
不相干的算法上，说明该签名没有反映算法自身的形态——这正是本约定要阻止的。

## 五族总表

| 算法族 | 典型算法 | 自然接口 | 对照版文件 | 对照对象 |
|---|---|---|---|---|
| 监督估计器 | 线性回归、逻辑回归、SVM、决策树、随机森林、朴素贝叶斯 | `Model.fit(X, y)` / `Model.predict(X)` | `framework.py` | sklearn 同接口 |
| 无监督估计器 | K-Means、PCA、AutoEncoder | `Model.fit(X)`（**无 y**）/ `predict` 或 `transform` / `encode`+`decode` | `framework.py` | sklearn 同接口；AutoEncoder 另可比 PCA |
| 搜索求解器 | A*、Minimax、MCTS | `solve(...) -> 解` / `search(state) -> action` | `baseline.py` | 基线算法（Dijkstra / 无剪枝版 / 随机策略） |
| 深度模型 · 判别式 | 感知机、MLP、LeNet、RNN/LSTM | `Model.fit(X, y)` / `predict`（内部前向+反向手写） | `framework.py` | **PyTorch 对照**（不是 sklearn） |
| 深度模型 · 生成式 | GAN、VAE、Diffusion、mini-Transformer、mini-GPT | `Model.train(data)` / `sample()` 或 `generate(prompt)` | `framework.py` | **PyTorch 对照** |
| 深度模型 · 组件 | Attention | `forward(...) / backward(...)` | `framework.py`（**对照的是数值梯度，不是框架实现**） | 中心差分梯度校验 |
| 流水线 | mini-RAG | 按链路组织（检索 → 生成） | `framework.py`（分环节对照） | 端到端指标 + 现成链 |

> 族的**接口**与**对照对象**由本表决定；族的**归属**若有争议，以第 1 条判据（有没有 y）为最终裁决。

## 文件形态的自由度

- 三件套（`impl.py` + 对照 + `demo.py`）是常见形态，不是强制形态
- 对照逻辑可以内嵌：如 minimax 的"有剪枝 vs 无剪枝"对比直接在 `impl.py`/`demo.py` 内部做，不需要单独 `baseline.py`
- 流水线族可以没有单一 `Model` 接口，按链路模块组织
- 组件族（Attention）没有 `fit`/`predict`，只有 `forward`/`backward`；其对照文件校验的是数值梯度
- **各族文件的首行 docstring 必须自陈族与接口**，格式：`"""<算法名> — 手写实现（<族> · <子类>）"""`，
  紧接着用 2~4 行说明"为什么本目录是这个形态"（如"无监督，所以没有 y"）
- 允许 README 加「目录形态」段（文件 × 角色 × 接口表格）说明本实验的实际形态；
  **该段的表格已由骨架填好，动手时按实际签名核对即可**，不必从零写

## 手写纪律的界限（按族细化）

| 族 | impl.py 允许 | impl.py 禁止 |
|---|---|---|
| 监督估计器 | numpy 矩阵运算、手写梯度 | `sklearn.*` 估计器、`scipy.optimize` 现成求解器 |
| 无监督估计器 | numpy 矩阵运算、手写迭代/特征分解 | `sklearn.*` 估计器（含 `KMeans`/`PCA`）、`scipy` 聚类与降维 |
| 搜索求解器 | 纯 Python 数据结构（heapq 等） | 现成图算法库（networkx 的 A* 等） |
| 深度模型 | `torch.Tensor`、`torch.autograd`（张量与求导是工具） | PyTorch 的现成层、现成优化器、`torchvision.models` |
| 流水线 | 各环节中已完成的算法实验代码 | 直接调 LangChain 等框架的现成链 |

> 注：本表用中文描述而非列举 API 名，是为了**让 `validate.py` 的属性调用扫描（它以
> `torch.nn` / `torch.optim` 等字面量为特征）只对真实代码报警**——docstring 里写出这些
> 字面量会被记为"疑似绕过手写纪律"的警告。写 impl.py 的 docstring 时请同样避免列举它们。

灰度判断：问自己"这一行调用的东西是不是本实验要理解的原理本身"——是，就必须手写；只是工具（求导、绘图、数据加载、评估指标）就可用库。

## 对照版本的选择逻辑

- **有同名框架接口**（sklearn/PyTorch 一行能调的）→ 框架对照，重点分析"框架多做了什么"（向量化、正则化、数值稳定性、并行）
- **没有现成框架接口**（搜索类）→ 基线对照，重点量化"本算法相对朴素基线的收益"（如 A* vs Dijkstra 的扩展节点数）
- **端到端系统**（RAG）→ 指标对照，消融实验（去掉某环节看指标掉多少）
