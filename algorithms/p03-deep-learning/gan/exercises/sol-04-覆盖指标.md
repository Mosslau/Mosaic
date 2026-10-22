# 参考解：第 4 题（实现）——覆盖指标

```python
def mode_coverage(samples, centers, threshold=0.35):
    d = norm(samples[:,None]-centers[None,:], axis=2)
    idx = d.argmin(1); close = d.min(1) < threshold
    counts = bincount(idx[close], minlength=len(centers))
    covered = sum(counts>0)
    p = counts/counts.sum()
    entropy = -sum(p[p>0]*log(p[p>0]))
    return covered, counts, entropy
```

两个近样本 + 一个远样本：覆盖 2，熵 `log 2`。
