# 参考解：第 3 题（判断）

| 变体 | 症状 |
|---|---|
| A encoder 加 causal | 源序列只能单向看，双向理解丢失 |
| B cross-attn K/V 用 decoder | decoder 不再看源序列，退化成语言模型 |
| C 训练用模型预测 | 暴露偏差/训练不稳；teacher forcing 才是并行稳定做法 |
