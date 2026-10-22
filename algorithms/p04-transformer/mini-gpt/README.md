# 迷你 GPT 字符级语言模型

> 状态：⬜ 未开始（骨架已就绪）
> 计划与范围见 [族级导读](../README.md)
> 对应文档章节：`../../docs/人工智能代表算法演进路线.md` 第 5.3.4 章

生成模型（深度模型 · 生成式）：入口 `MiniGPT(vocab_size, n_layers, d_model, n_heads, context).train(text)` / `generate(prompt, n_steps, temperature, top_k)`，实现在 [impl.py](impl.py)，对照是 [framework.py](framework.py) 的 PyTorch mini-GPT。**没有 `fit(X,y)`**：目标是 next-token，输入/目标来自同一段文本的错位切分。

## 本实验要解决什么

把 attention + Block 串成字符级 GPT：

1. `CharTokenizer`：字符↔id、`<unk>`、可复现字符表；
2. token embedding + 可学习位置嵌入；
3. N 个 Transformer Block（复用上一实验）；
4. 输出投影 + 交叉熵 + 全链路反向；
5. 采样：greedy / temperature / top-k；
6. 小语料训练 + prompt 生成，观察“记忆/重复/泛化”。

## 计划交付

- 实现：tokenizer、embedding、N 个 Block、LM head、采样；
- 测试：tokenizer roundtrip、causal 不变性、loss 下降、生成形状/确定性；
- 素材：loss 曲线、不同 temperature/top-k 生成文本、注意力热图、生成 GIF；
- 练习 5 题；项目：prompt 生成 + 采样策略对比；
- README：基础篇 8 节 + 进阶篇六段 + 五级清单。

## 数据与环境

默认 **Zen of Python / 合成 grammar（1–5KB）**，离线可跑；可选 Tiny Shakespeare。
`d_model=32/64`、`n_heads=2/4`、`context=16/32`、`n_layers=1/2`；CPU。

## 边界

只做字符级小 GPT；不做 BPE、BERT/T5、预训练+微调、KV cache、长上下文、
分布式/量化部署；这些在"局限与延伸"里说明。

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
