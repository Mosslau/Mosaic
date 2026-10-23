# 参考解：第 3 题（判断）

| 变体 | 症状 |
|---|---|
| A 直接采样反传 | 采样不可导，编码器收不到梯度 |
| B 不加 KL | latent 不接近先验，采样出垃圾 |
| C beta 极大 | posterior collapse，latent 被忽略、重构模糊 |
