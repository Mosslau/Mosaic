# 迁移项目：Block next-token 续写

## 需求

把 Block 从“能训练”推进到“能续写”：

1. 在合成语料上训练 pre-LN Block；
2. 用 `predict_next` 连续预测 40 个字符；
3. 报告测试 next-token 准确率与续写结果。

## 功能清单

- [x] 字符级 tokenizer
- [x] 40 轮 next-token 训练
- [x] `predict_next` 自回归续写
- [x] 验收断言

## 验收标准

1. 测试 next-token acc **> 0.7**；
2. 续写长度 > prompt 长度（能持续生成）。

## 运行方式

```bash
cd algorithms/p04-transformer/mini-transformer/project
uv run python next_token.py
```

## 实测结果（已验证）

测试 next-token acc **0.793**；prompt `"the cat"` 可续写出符合语料模板的短语
（具体文本随训练/采样略有差异）。

## 结论

Block 学到的是**局部 next-token 转移**：它能续出语法模板，但不代表理解语义。
这也是“Block ≠ GPT”的原因：GPT 还需要更大语料、更多层、采样策略与评估。
