# 参考解：第 1 题（说清）

1. `Z=A_prev W+b`，`A=ReLU(Z)`；输出层 `logits=A W+b`，`p=softmax(logits)`。
2. softmax + 交叉熵对 logits 的梯度是 `p−y`；对一个 batch 取平均即 `(p−y)/n`。
3. 隐层收到 `dA=dZ @ W.T`，还要乘本层激活导数 `relu_grad(Z)`，才是 `dZ`。
4. 全零初始化时所有隐单元前向/梯度完全相同，对称性无法打破，网络等价于一个线性模型。
