# 参考解：第 4 题（实现）——全局梯度裁剪

```python
def clip_gradients(grads, clip):
    norm = sqrt(sum((g**2).sum() for g in grads.values()))
    if norm > clip:
        scale = clip / (norm + 1e-12)
        return {k: g * scale for k, g in grads.items()}, norm
    return grads, norm
```

裁剪后范数 = clip；所有梯度同乘一个正数，方向不变。
