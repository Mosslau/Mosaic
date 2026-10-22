# 参考解：第 4 题（实现）——多头拆/拼

```python
def split_heads(X, H):
    N,T,D = X.shape
    return X.reshape(N,T,H,D//H).transpose(0,2,1,3)

def merge_heads(X):
    N,H,T,Dh = X.shape
    return X.transpose(0,2,1,3).reshape(N,T,H*Dh)
```

roundtrip 应逐位一致；注意 transpose 的轴顺序。
