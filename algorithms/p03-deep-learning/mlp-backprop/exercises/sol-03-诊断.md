# 参考解：第 3 题（判断）

| 变体 | 症状 | 诊断 |
|---|---|---|
| A 前向不做 ReLU | 多层网络退化成线性模型，XOR 精度接近 0.5 | monkeypatch `relu`/`relu_grad` 为恒等 |
| B softmax 不减最大值 | `exp(1000)` 溢出 → inf/nan | 直接算 `np.exp([1000,1001])` 看警告 |
| C 全零初始化 | 所有隐单元相同，测试 acc≈0.1（10 类） | 正常训练，看 loss 不降 |

运行 `uv run python sol-03-诊断.py` 看数字。
