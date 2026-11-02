"""GCN 的无图 MLP 基线（独立实现）。

用途：回答"图结构到底带来了多少收益"。
- 与 `impl.py` 的 GCN 使用**同一份特征、同一个 train_mask、同一套优化设置**；
- 不 import `impl.py` 的 GCN，也不使用邻接矩阵——只把节点特征当独立样本；
- 训练/评估协议与 demo 一致，便于直接比较测试 acc。

这不是一个"更强的模型"，而是一个**公平的消融基线**：如果 GCN 赢不了它，
说明收益来自特征而不是图结构。
"""

from __future__ import annotations

import numpy as np


def mlp_fit_predict(X, y, train_mask, hidden=16, epochs=200, lr=0.1, seed=0):
    """无图 MLP：只用节点特征做半监督节点分类。

    参数与 GCN 对齐：同样的 hidden、epochs、lr、seed；
    只在 train_mask 上计算交叉熵，返回全部节点的预测。
    """
    rng = np.random.default_rng(seed)
    n, d = X.shape
    W1 = rng.normal(0, np.sqrt(2 / d), (d, hidden))
    b1 = np.zeros(hidden)
    W2 = rng.normal(0, np.sqrt(2 / hidden), (hidden, 2))
    b2 = np.zeros(2)
    for _ in range(epochs):
        H = np.maximum(0, X @ W1 + b1)
        z = H @ W2 + b2
        z -= z.max(1, keepdims=True)
        p = np.exp(z) / np.exp(z).sum(1, keepdims=True)
        G = np.zeros_like(p)
        G[train_mask] = p[train_mask] - np.eye(2)[y[train_mask]]
        G /= train_mask.sum()
        dW2 = H.T @ G
        db2 = G.sum(0)
        dH = (G @ W2.T) * (H > 0)
        dW1 = X.T @ dH
        db1 = dH.sum(0)
        for p_, g_ in ((W1, dW1), (b1, db1), (W2, dW2), (b2, db2)):
            p_ -= lr * g_
    H = np.maximum(0, X @ W1 + b1)
    return (H @ W2 + b2).argmax(1)


if __name__ == "__main__":
    raise SystemExit("本文件是基线库，入口是 demo.py：uv run python demo.py")
