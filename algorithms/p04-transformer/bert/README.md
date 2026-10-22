# BERT / 掩码语言模型（encoder-only）

> 状态：⬜ 未开始（骨架已就绪）
> 计划与范围见 [族级导读](../README.md)
> 对应文档章节：`../../docs/人工智能代表算法演进路线.md` 第 5.3.2 章

Encoder-only 模型（深度模型 · 预训练/表示）：入口 `BertMLM(d_model, n_heads, n_layers).train(tokens)` / `encode(tokens)` / `predict_masked(tokens)`，实现在 [impl.py](impl.py)，对照是 [framework.py](framework.py) 的 PyTorch encoder + MLM。**没有 `fit(X,y)`，也没有 `generate`**：目标是恢复被 mask 的 token，不是自回归生成。

## 本实验要解决什么

同一个 Block，去掉 causal mask，改成**双向**看整句；再用 **MLM** 训练：

1. 15% token 被 mask（80% `[MASK]` / 10% 随机 / 10% 不变）；
2. 只对被 mask 的位置算交叉熵；
3. `[CLS]` 的表示接线性分类器做小样本探针；
4. 与 GPT 对照：双向表示 vs 因果生成。

## 计划交付

- 实现：BERT encoder（非 causal）、MLM head、`[CLS]` 分类探针；
- 测试：mask 不泄漏、只算 masked loss、梯度检查、分类探针；
- 素材：MLM loss/准确率、attention 热图、`[CLS]` 表示可视化；
- 练习 5 题；项目：小语料 MLM + 分类探针；
- README：基础篇 8 节 + 进阶篇六段 + 五级清单。

## 数据与环境

默认 Zen/合成句子；字符级或小词表；`d_model=32/64`、`n_heads=2/4`、`n_layers=1/2`；
CPU；torch 只做对照。

## 边界

只做小规模 MLM + 线性探针；不做 BERT 全量预训练/多任务微调、
不做 BPE/WordPiece、不做大模型分布式训练。

# 进阶篇 · 实验档案

## 1. 设计原理

（待实现：双向 encoder、MLM 目标、与 GPT 的对照。）

## 2. 数学推导

（待实现：MLM 交叉熵、mask 选择、非 causal attention、分类探针。）

## 3. 手写实现要点

（待实现：mask 位置、只对 masked 计损、共享 embedding/输出、梯度检查。）

## 4. 框架对照

（待实现：PyTorch encoder + MLM 的接口与差异。）

## 5. 实验结果

（待实现：MLM loss/准确率、探针 acc、手写 vs 框架、验证声明。）

## 6. 局限与延伸

（待实现：小语料、字符级、无全量预训练；下游 BERT 变体。）
