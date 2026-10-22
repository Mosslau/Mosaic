# 参考解：第 4 题（实现）——两种 mask

```python
enc = np.ones((T,T), dtype=bool)
dec = np.tril(np.ones((T,T), dtype=bool))
```

encoder 全 1；decoder 下三角，上三角为 0。
