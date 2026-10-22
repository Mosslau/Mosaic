# 练习：T5 / encoder-decoder

> 用法：先自己做，再看 `sol-NN-*` 参考解。题目按五级能力分级，**本文件不附答案**。
> 前置：读完 [../README.md](../README.md) 的基础篇。

| 题 | 级别 | 参考解 |
|---|---|---|
| 1 | 说清 | `sol-01-概念.md` |
| 2 | 走通 | `sol-02-手算.md` |
| 3 | 判断 | `sol-03-诊断.md` |
| 4 | 实现 | `sol-04-mask.md` + `sol-04-mask.py`（可运行） |
| 5 | 迁移 | `sol-05-copy-reverse.md` |

---

## 第 1 题（说清）encoder/decoder/cross-attn

**目标**：能力 1——复述三者的分工。

**要求**：

1. encoder 用什么 mask？
2. decoder self-attn 用什么 mask？
3. cross-attn 的 Q/K/V 来自哪？
4. teacher forcing 的输入/目标怎么错位？

**验收标准**：全 1；下三角；Q=decoder，K/V=encoder；`[BOS]+tgt[:-1]` → `tgt`。

## 第 2 题（走通）mask 与 CE

**目标**：能力 2——手算 mask/CE。

**要求**：

1. 目标长度 5，decoder 第 3 个位置能看哪些位置？
2. 正确 token 概率 0.8，单点 CE？
3. 5 个位置平均？

**验收标准**：0/1/2/3；0.223；平均。

## 第 3 题（判断）三个“看起来能跑”的实现

**目标**：能力 3——从生成/注意力反推错误。

**要求**：

- **A**：encoder 也加 causal mask；
- **B**：cross-attn 的 K/V 用 decoder hidden；
- **C**：训练时 decoder 输入用模型自己的预测。

分别回答症状。

**验收标准**：A 源信息单向；B 不看源；C 训练不稳/暴露偏差。

## 第 4 题（实现）两种 mask

**目标**：能力 4——实现 encoder 全 1 / decoder 下三角。

**要求**：

1. `(T,T)` 全 1；
2. `(T,T)` 下三角；
3. 验证 decoder 上三角为 0。

**验收标准**：形状正确；上三角为 0。

## 第 5 题（迁移）copy/reverse

**目标**：能力 5——训练并评测 seq2seq。

**要求**：

1. 700 训练 / 200 测试；
2. copy/reverse 各半；
3. greedy 生成；
4. exact 匹配率。

**验收标准**：exact >0.9；说明 toy 任务不代表真实翻译。
