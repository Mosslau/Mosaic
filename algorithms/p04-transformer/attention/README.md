# 注意力机制 Scaled Dot-Product Attention

> 状态：⬜ 未开始（骨架已就绪）
> 计划与范围见 [族级导读](../README.md)
> 对应文档章节：`../../docs/人工智能代表算法演进路线.md` 第 5.2 章

注意力组件（深度模型 · 组件）：入口是 `ScaledDotProductAttention().forward(Q, K, V, mask)` → `(out, weights)` 与 `backward(d_out)` → `(dQ, dK, dV)`，实现在 [impl.py](impl.py)；对照是 [framework.py](framework.py) 的 PyTorch 注意力。**没有 `fit` / `train`**：它不是独立模型，而是 Block/GPT 的组件。

## 本实验要解决什么

让每个位置直接“看”其他位置：`Attention(Q,K,V)=softmax(QKᵀ/√d_k)V`。
重点不是调用 `nn.MultiheadAttention`，而是手写：

1. Q/K/V 投影与多头拆分/拼接；
2. padding mask 与 causal mask（`-1e9`，不用 `-inf`）；
3. 数值稳定 softmax；
4. softmax 的雅可比 + 对 Q/K/V 的反向；
5. 为什么除以 `√d_k`（点积方差随维度增长）。

## 计划交付

- 实现：单头 scaled dot-product、causal/padding mask、多头；
- 测试：形状、权重行和=1、causal 不影响过去、有限差分 `dQ/dK/dV`、mask nan；
- 素材：注意力热图、causal mask 图、权重动画 GIF；
- 练习 5 题；项目：attention pooling 做序列分类/对齐；
- README：基础篇 8 节 + 进阶篇六段 + 五级清单。

## 数据与环境

合成 Q/K/V 与小序列（可构造 mask）；`uv sync --extra deep-learning --extra dev`；
numpy 手写，torch 只做 `framework.py` 对照；CPU。

## 边界

只做单头/多头注意力组件；不做完整 Block/GPT（下一实验）、不做 BERT/T5、
不做 FlashAttention/长上下文优化。

# 进阶篇 · 实验档案

## 1. 设计原理

（待实现：本实验解决什么问题、核心思想、与前一实验的依赖。）

## 2. 数学推导

（待实现：关键公式、mask/softmax/LayerNorm 的反向推导。）

## 3. 手写实现要点

（待实现：缓存、mask、数值稳定、梯度检查、易错点。）

## 4. 框架对照

（待实现：PyTorch 对照接口与差异分析。）

## 5. 实验结果

（待实现：数据、指标、手写 vs 框架、可视化结论、验证声明。）

## 6. 局限与延伸

（待实现：失效边界、未覆盖范围、下游方向。）
