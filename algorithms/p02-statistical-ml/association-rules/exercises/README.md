# 练习：关联规则

> 先做题，再看 `sol-NN-*`；本文件不附答案。

| 题 | 级别 | 参考解 |
|---|---|---|
| 1 | 说清 | `sol-01-概念.md` |
| 2 | 走通 | `sol-02-手算.md` |
| 3 | 判断 | `sol-03-诊断.md` |
| 4 | 实现 | `sol-04-support.md` + `sol-04-support.py` |
| 5 | 迁移 | `sol-05-筛选.md` |

## 1 说清

解释 support / confidence / lift，以及 Apriori 反单调性。

## 2 走通

5 个篮子手算 `support({a,b})`、`confidence(a→b)`、`lift`。

## 3 判断

- A：只按 confidence 排序；
- B：min_support=0；
- C：把共现当因果。

分别说症状。

## 4 实现

实现 `support(itemset)` 与 `confidence(A→B)`，在 5 个篮子上与手算一致。

## 5 迁移

用 Apriori 挖规则，按 lift/confidence 过滤，写 3 条建议并说明局限。
