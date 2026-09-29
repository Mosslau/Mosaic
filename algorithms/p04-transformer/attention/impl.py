"""注意力机制 — 手写实现（深度模型 · 组件）

**本目录不是一个可独立训练的模型，而是一个组件**——所以它既没有
fit(X, y)，也没有 train(data)/sample()，而是**前向 + 反向的模块形态**。
这一点必须写在最前面，否则读者会拿它和 mlp-backprop 比接口。

    attn = ScaledDotProductAttention()
    out, weights = attn.forward(Q, K, V, mask=None)     # 顺带返回注意力权重
    dQ, dK, dV = attn.backward(d_out)

手写纪律：本实现用 numpy；若用 torch 仅允许 `torch.Tensor` / `torch.autograd`，
**禁止 PyTorch 的现成多头注意力与现成注意力函数**——那正是本章要手写的原理。

三个必须自己推出的点（README「数学推导」段）：
    1. 为什么要除以 sqrt(d_k)：点积方差随 d_k 增长，softmax 会被推向饱和区
    2. softmax 的雅可比矩阵（反向传播的推导核心）
    3. mask 的两种用法：padding mask（屏蔽填充位）与 causal mask（自回归防偷看）
"""

import numpy as np


class ScaledDotProductAttention:
    """Attention(Q,K,V) = softmax(Q K^T / sqrt(d_k)) V。"""

    def __init__(self, causal: bool = False) -> None:
        self.causal = causal
        self.cache: dict = {}

    def forward(self, Q: np.ndarray, K: np.ndarray, V: np.ndarray,
                mask: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """返回 (输出, 注意力权重矩阵)——权重是可视化的对象，必须能拿到。"""
        # TODO: 手写
        #   1. scores = Q @ K.swapaxes(-1, -2) / sqrt(d_k)
        #   2. causal 时构造上三角掩码（**用 -1e9 而不是 -inf，避免 softmax 出 nan**）
        #   3. weights = softmax(scores)；输出 = weights @ V
        #   4. 缓存 scores / weights / Q / K / V 供反向使用
        raise NotImplementedError("TODO: 手写缩放点积注意力前向")

    def backward(self, d_out: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """返回 (dQ, dK, dV)；softmax 的反向是本章推导的核心，不能跳过。"""
        # TODO: 手写
        #   dV = weights.T @ d_out
        #   d_weights = d_out @ V.T
        #   softmax 反向：d_scores = weights * (d_weights - (d_weights * weights).sum(-1, keepdims=True))
        #   dQ = d_scores @ K / sqrt(d_k)；dK = d_scores.T @ Q / sqrt(d_k)
        raise NotImplementedError("TODO: 手写注意力反向传播")


class MultiHeadAttention:
    """多头：把 d_model 切成 n_heads 份并行做注意力，再拼接后过输出投影。"""

    def __init__(self, d_model: int = 64, n_heads: int = 4, causal: bool = False) -> None:
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        self.causal = causal
        self.params: dict = {}

    def forward(self, X: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
        # TODO: 手写——线性投影出 Q/K/V → 分头（reshape + transpose）→ 各头注意力 → 拼接 → 输出投影
        #   分头/合头的 transpose 顺序最容易写错，README「手写实现要点」要写清形状变化
        raise NotImplementedError("TODO: 手写多头注意力前向")

    def backward(self, d_out: np.ndarray) -> dict:
        # TODO: 手写——输出投影反向 → 拆头 → 各头反向 → 合并 dQ/dK/dV → 输入投影反向
        raise NotImplementedError("TODO: 手写多头注意力反向")


if __name__ == "__main__":
    raise SystemExit("请先完成 forward/backward，再到 demo.py 跑实验")
