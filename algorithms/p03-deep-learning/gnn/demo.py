"""GCN — demo：图上的半监督节点分类 vs 只用特征的 MLP"""

from __future__ import annotations

import time

import numpy as np
from impl import GCN, make_sbm


def mlp_fit_predict(X, y, train_mask, hidden=16, epochs=200, lr=0.1, seed=0):
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


def main() -> None:
    A, X, y = make_sbm(30, 0.2, 0.08, 8, seed=0)
    n = len(y)
    train = np.zeros(n, bool)
    for c in (0, 1):
        train[np.where(y == c)[0][:6]] = True
    print(f"节点 {n}，边 {int(A.sum() // 2)}，训练节点 {train.sum()}，测试 {n-train.sum()}")
    for name, pred, t in (
        ("GCN", None, None),
        ("MLP", None, None),
    ):
        pass
    t0 = time.perf_counter()
    gcn = GCN(16, 2, 0.2, 200, 0).fit(A, X, y, train)
    gcn._X = X
    pg = gcn.predict()
    t_g = time.perf_counter() - t0
    pm = mlp_fit_predict(X, y, train)
    print(f"\n{'模型':8} | {'测试 acc':>8} | {'末轮 loss':>9}")
    print("-" * 34)
    print(f"{'GCN':8} | {(pg[~train] == y[~train]).mean():8.4f} | {gcn.loss_history[-1]:9.4f}")
    print(f"{'MLP':8} | {(pm[~train] == y[~train]).mean():8.4f} | {'—':>9}")
    print(f"\nGCN loss {gcn.loss_history[0]:.3f} → {gcn.loss_history[-1]:.3f}；{t_g*1000:.0f}ms")
    assert (pg[~train] == y[~train]).mean() > 0.75


if __name__ == "__main__":
    main()
