# 参考解：第 4 题（实现）——KL 闭式

```python
kl = -0.5 * np.sum(1 + lv - mu**2 - np.exp(lv), axis=1)
kl_mean = kl.mean()
```

对 μ：`mu / N`（batch 平均）；对 lv：`0.5*(exp(lv)-1)/N`。
