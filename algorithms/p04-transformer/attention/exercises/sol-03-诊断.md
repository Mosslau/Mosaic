# 参考解：第 3 题（判断）

| 变体 | 症状 |
|---|---|
| A mask 用 `-inf` | 整行被 mask 时 softmax 出 nan |
| B 反向不清零 mask | 未来/填充位置仍然收到梯度 |
| C 不除 `√d_k` | 高维点积方差大，softmax 接近 one-hot，梯度消失 |
