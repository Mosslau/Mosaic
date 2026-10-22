# 练习：注意力机制

> 用法：先自己做，再看 `sol-NN-*` 参考解。题目按五级能力分级，**本文件不附答案**。
> 前置：读完 [../README.md](../README.md) 的基础篇。

| 题 | 级别 | 参考解 |
|---|---|---|
| 1 | 说清 | `sol-01-概念.md` |
| 2 | 走通 | `sol-02-手算.md` |
| 3 | 判断 | `sol-03-诊断.md` |
| 4 | 实现 | `sol-04-多头.md` + `sol-04-多头.py`（可运行） |
| 5 | 迁移 | `sol-05-检索.md` + `sol-05-检索.py`（可运行） |

---

## 第 1 题（说清）Q/K/V、缩放、mask

**目标**：能力 1——复述 attention 的四个量。

**要求**：写出：

1. `Attention(Q,K,V)` 公式；
2. 为什么除以 `√d_k`；
3. padding mask / causal mask 各屏蔽什么；
4. 为什么 mask 用 `-1e9` 而不是 `-inf`。

**验收标准**：公式、方差、两种 mask、nan 风险。

## 第 2 题（走通）两个 token 的手算

**目标**：能力 2——手算 softmax 权重与输出。

**要求**：`Q=K=[[1,0],[0,1]]`，`V=[[1,0],[0,1]]`，`d_k=2`：

1. 分数矩阵；
2. softmax 后两行；
3. 输出；
4. causal 下第二行输出。

**验收标准**：`[0.669,0.331]` 与 `[0.331,0.669]`；causal 第二行 `[0,1]`。

## 第 3 题（判断）三个“看起来能跑”的实现

**目标**：能力 3——从权重/梯度/nan 反推错误。

**要求**：

- **A**：mask 用 `-inf`；
- **B**：反向时不对 mask 位置清零；
- **C**：不除 `√d_k`。

分别回答：症状是什么？

**验收标准**：A 全 mask 行 nan；B 未来/填充位收梯度；C 高维 softmax 饱和。

## 第 4 题（实现）多头拆/拼

**目标**：能力 4——实现 `split_heads` / `merge_heads` 并验证可逆。

**要求**：

1. `(N,T,H,dh) → (N,H,T,dh)`；
2. 再拼回 `(N,T,H*dh)`；
3. 与输入逐位一致。

**验收标准**：roundtrip 误差 <1e-12。

## 第 5 题（迁移）内容检索

**目标**：能力 5——用 attention 做 key-value 检索。

**要求**：

1. 随机 64 个 key/value；
2. 50 个 query，每个等于某个 key；
3. 比较 attention 与 mean pooling 的 top-1。

**验收标准**：attention >0.95；mean pooling <0.1。

---

## 参考解运行记录

```bash
cd algorithms/p04-transformer/attention/exercises
uv run python sol-04-多头.py
uv run python sol-05-检索.py
```

**2026-10-22 复跑（uv 环境，Python 3.13.15 / numpy 2.5.4）观察结果**：

- `sol-04`：roundtrip 最大差 0.00e+00；
- `sol-05`：T=64、D=32、64 个 query 全量 top-1 = 1.000。
