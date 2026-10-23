# 参考解：第 4 题（实现）——余弦 top-k

```python
X = X / np.linalg.norm(X, axis=1, keepdims=True)
q = q / np.linalg.norm(q)
scores = X @ q
order = np.argsort(scores)[::-1][:k]
```

归一化后内积 = 余弦。
