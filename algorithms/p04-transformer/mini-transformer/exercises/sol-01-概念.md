# 参考解：第 1 题（说清）

pre-LN Block：

```text
x = x + MultiHeadAttention(LN1(x))
x = x + FFN(LN2(x))
```

- LN：稳定数值/尺度；
- MHA：每个位置按内容看其他位置；
- FFN：逐位置非线性加工；
- 残差：保留原表示，给梯度直连路径；
- pre-LN：LN 在子层前，主路恒等，深层更稳。
