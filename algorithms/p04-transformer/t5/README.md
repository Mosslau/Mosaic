# T5 / 编码器-解码器（encoder-decoder）

> 状态：⬜ 未开始（骨架已就绪）
> 计划与范围见 [族级导读](../README.md)
> 对应文档章节：`../../docs/人工智能代表算法演进路线.md` 第 5.3.3 章

Encoder-decoder 模型（深度模型 · 生成式）：入口 `T5Toy(d_model, n_heads, n_layers).train(pairs)` / `generate(src)`，实现在 [impl.py](impl.py)，对照是 [framework.py](framework.py) 的 PyTorch encoder-decoder。**没有 `fit(X,y)`**：`pairs=(src,tgt)`，训练目标是 decoder 的 next-token。

## 本实验要解决什么

把“读源序列”和“写目标序列”分成两个栈：

1. **encoder**：双向 self-attention，读完整源序列；
2. **decoder**：causal self-attention + **cross-attention** 看 encoder；
3. 训练：teacher forcing，目标序列右移一位；
4. 推理：从 `<bos>` 开始自回归 `generate`；
5. toy 任务：copy / reverse / 小型翻译对。

## 计划交付

- 实现：encoder block、decoder block（self + cross + FFN）、生成循环；
- 测试：causal mask、cross-attention 形状、teacher forcing 错位、梯度检查；
- 素材：attention/cross-attention 热图、loss、生成样例、GIF；
- 练习 5 题；项目：copy/reverse/翻译 toy 任务；
- README：基础篇 8 节 + 进阶篇六段 + 五级清单。

## 数据与环境

默认合成 `(src,tgt)` 对（copy/reverse/数字翻译）；`d_model=32/64`、`n_heads=2/4`、
`n_layers=1/2`；CPU；torch 只做对照。

## 边界

只做 toy seq2seq 与 cross-attention 原理；不做 T5 全量预训练/多任务/
大规模翻译、BPE、长上下文、KV cache/部署。

# 进阶篇 · 实验档案

## 1. 设计原理

（待实现：encoder-decoder、cross-attention、teacher forcing。）

## 2. 数学推导

（待实现：双向 encoder mask、decoder causal mask、cross-attention 梯度。）

## 3. 手写实现要点

（待实现：src/tgt 错位、mask、cross-attention 的 K/V 来自 encoder、生成停止条件。）

## 4. 框架对照

（待实现：PyTorch encoder-decoder 的接口与差异。）

## 5. 实验结果

（待实现：copy/reverse 准确率、生成样例、手写 vs 框架、验证声明。）

## 6. 局限与延伸

（待实现：toy 任务、无大规模预训练；T5/BART 全量模型。）
