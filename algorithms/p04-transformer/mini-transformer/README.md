# 迷你 Transformer Block

> 状态：⬜ 未开始（骨架已就绪）
> 计划与范围见 [族级导读](../README.md)
> 对应文档章节：`../../docs/人工智能代表算法演进路线.md` 第 5.2 章

Transformer Block（深度模型 · 组件/可训练块）：入口 `TransformerBlock(d_model, n_heads, d_ff).forward(X, mask)` / `backward`，并可在字符序列上 `train(tokens)`；实现在 [impl.py](impl.py)，对照是 [framework.py](framework.py) 的 PyTorch Block。**没有 `fit(X,y)`**：语言建模的输入/目标是同一段文本的错位切分。

## 本实验要解决什么

把 attention 组装成可堆叠的 Block：

1. LayerNorm 前向/反向（三项梯度，别漏方差项）；
2. 多头注意力 + 输出投影；
3. 逐位置 FFN（两层 MLP）；
4. 残差 + **pre-LN**：`x=x+Attn(LN(x))`，`x=x+FFN(LN(x))`；
5. 可学习位置嵌入；
6. 小语料 next-token 训练，验证 Block 真的能学。

## 计划交付

- 实现：LayerNorm、MultiHeadAttention、FFN、残差、pre-LN、位置嵌入；
- 测试：LN/Block 有限差分、残差开关、causal 性质、loss 下降；
- 素材：有无残差/预 LN 的 loss 对比、注意力热图、结构 Mermaid（不是 PNG）；
- 练习 5 题；项目：toy 语料上的 next-token Block；
- README：基础篇 8 节 + 进阶篇六段 + 五级清单。

## 数据与环境

合成字符序列 / Zen of Python；`d_model=32/64`、`n_heads=2/4`、`context=16/32`；
CPU；torch 只做对照。

## 边界

只做单层/两层 Block 与 pre-LN；不做 BERT/T5、不做大规模预训练、
不做 KV cache/长上下文优化。

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
