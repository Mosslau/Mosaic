# MLP 与手写反向传播

> 状态：⬜ 未开始
> 计划与补强范围见 [族级导读](../README.md)
> 深度模型（判别式）：入口 `MLP(hidden_sizes, lr, epochs).fit(X, y)` / `predict_proba(X)`，实现在 [impl.py](impl.py)；对照是 [framework.py](framework.py) 的 PyTorch MLP。
> 对应文档章节：`../../docs/人工智能代表算法演进路线.md` 第 4.2 章

## 设计原理

（这个算法要解决什么问题？核心思想一句话概括。它为什么比之前的方法好？）

## 数学推导

（关键公式与推导过程，手推一遍再写代码）

## 手写实现要点

（numpy 手写实现时的关键步骤、容易踩的坑 —— impl.py）

## 框架对照

（对应 sklearn / PyTorch / 其他框架的接口是哪个？framework.py）
（框架内部做了什么手写版没做的优化？如正则化、向量化、并行、数值稳定性处理）

## 实验结果

（数据集、评价指标、可视化结论）
（**手写 vs 框架结果对比**：指标差异、耗时差异、差异原因分析）

## 局限与延伸

（这个算法的边界在哪里？它引出了哪个后续算法？）

## 计划补强（P0）

- 实验四：优化器（SGD / Momentum / Adam）、初始化（零/随机/He/Xavier）、
  正则（weight decay / dropout / early stopping）、**学习率 schedule + batch size**；
- 梯度检查：有限差分验证手写反向传播；
- 目标：不只"能收敛"，还要看不同训练技巧对收敛速度/泛化的影响。
