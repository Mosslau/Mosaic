# 参考解：第 4 题（实现）——CFG

```python
eps = eps_un + w * (eps_c - eps_un)
```

- w=0 → 无条件；
- w=1 → 条件；
- w>1 → 强化条件。
