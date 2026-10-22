# 迁移项目：copy/reverse seq2seq 生成

## 需求

把 encoder-decoder 用到 toy seq2seq：

1. 训练源序列 → 目标序列；
2. copy：目标=源；
3. reverse：目标=源倒序；
4. 测试 exact 匹配率。

## 功能清单

- [x] 字符 Vocab + 任务 token
- [x] encoder 双向 / decoder causal + cross-attn
- [x] teacher forcing 训练
- [x] greedy 生成 + exact 评测

## 验收标准

1. test exact **> 0.9**；
2. copy/reverse 都能生成。

## 运行方式

```bash
cd algorithms/p04-transformer/t5/project
uv run python copy_reverse.py
```

## 实测结果（已验证）

- train token acc **1.000**；
- test exact **0.980**（copy 0.970 / reverse 0.990）。

## 结论

copy 考对齐，reverse 考重排；两者共享 encoder，靠 `<copy>/<rev>` 任务 token 区分。
toy 任务成功不代表真实翻译/摘要能力。
