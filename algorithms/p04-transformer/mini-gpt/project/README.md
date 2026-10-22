# 迁移项目：多 prompt / 多采样策略生成

## 需求

把 Mini-GPT 用到“给定 prompt 生成”的场景：

1. 训练字符级 GPT；
2. 对 `"the cat"`、`"a dog"` 两个 prompt；
3. 分别用 greedy、T=0.8、top-k=5 生成 36 字符；
4. 比较稳定性与多样性。

## 功能清单

- [x] 字符 tokenizer
- [x] 2 层 Mini-GPT
- [x] greedy / temperature / top-k
- [x] 验收断言

## 验收标准

1. test next-token acc **> 0.85**；
2. 每个 prompt、每种策略都能生成非空文本。

## 运行方式

```bash
cd algorithms/p04-transformer/mini-gpt/project
uv run python generate.py
```

## 实测结果（已验证）

test next-token acc **0.899**。

- greedy 最稳定，可能重复模板；
- T=0.8 有变化但基本连贯；
- top-k=5 比纯 temperature 更稳，多样性略低。

## 结论

温度/top-k 不是“提高准确率”的开关，而是**质量-多样性权衡**；
小语料模型容易背模板，生成通顺不等于理解。
