"""GCN — demo：图上的半监督节点分类 vs 只用特征的 MLP"""

from __future__ import annotations

import time

import numpy as np
from baseline import mlp_fit_predict
from impl import GCN, make_sbm


def main() -> None:
    A, X, y = make_sbm(30, 0.2, 0.08, 8, seed=0)
    n = len(y)
    train = np.zeros(n, bool)
    for c in (0, 1):
        train[np.where(y == c)[0][:6]] = True
    print(f"节点 {n}，边 {int(A.sum() // 2)}，训练节点 {train.sum()}，测试 {n-train.sum()}")
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
