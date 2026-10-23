"""图神经网络 GCN — 手写实现（半监督节点分类）"""

from __future__ import annotations

import numpy as np


def normalize_adj(A):
    """A_hat = D^{-1/2}(A+I)D^{-1/2}。"""
    A = np.asarray(A, dtype=float)
    if A.ndim != 2 or A.shape[0] != A.shape[1]:
        raise ValueError("A 应为方阵")
    A = A + np.eye(len(A))
    d = A.sum(1)
    dinv = 1.0 / np.sqrt(np.maximum(d, 1e-12))
    return A * dinv[:, None] * dinv[None, :]


class GCN:
    def __init__(self, hidden=16, n_classes=2, lr=0.1, epochs=100, seed=0):
        if hidden < 1 or epochs < 1 or lr <= 0:
            raise ValueError("参数非法")
        self.hidden, self.n_classes, self.lr, self.epochs, self.seed = \
            hidden, n_classes, lr, epochs, seed

    def fit(self, A, X, y, train_mask):
        A = np.asarray(A, dtype=float)
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 2 or len(X) != len(A) or len(y) != len(A):
            raise ValueError("A/X/y 形状不匹配")
        if not train_mask.any():
            raise ValueError("train_mask 不能全 False")
        self._X = np.asarray(X, dtype=float)
        rng = np.random.default_rng(self.seed)
        self.A_hat = normalize_adj(A)
        n, d = X.shape
        self.W1 = rng.normal(0, np.sqrt(2 / d), (d, self.hidden))
        self.b1 = np.zeros(self.hidden)
        self.W2 = rng.normal(0, np.sqrt(2 / self.hidden), (self.hidden, self.n_classes))
        self.b2 = np.zeros(self.n_classes)
        self.loss_history = []
        Y = np.eye(self.n_classes)[y]
        for _ in range(self.epochs):
            H1 = self.A_hat @ X @ self.W1 + self.b1
            Z1 = np.maximum(0, H1)
            logits = self.A_hat @ Z1 @ self.W2 + self.b2
            p = _softmax(logits)
            loss = -np.mean(np.log(np.clip(p[train_mask, y[train_mask]], 1e-12, 1)))
            self.loss_history.append(float(loss))
            # 只对训练节点回传
            G = np.zeros_like(p)
            G[train_mask] = p[train_mask] - Y[train_mask]
            G /= train_mask.sum()
            dW2 = (self.A_hat @ Z1).T @ G
            db2 = G.sum(0)
            dZ1 = self.A_hat @ G @ self.W2.T
            dH1 = dZ1 * (H1 > 0)
            dW1 = (self.A_hat @ X).T @ dH1
            db1 = dH1.sum(0)
            for p_, g_ in ((self.W1, dW1), (self.b1, db1),
                           (self.W2, dW2), (self.b2, db2)):
                p_ -= self.lr * g_
        return self

    def predict(self, A=None, X=None):
        if not hasattr(self, "W1"):
            raise RuntimeError("模型尚未训练")
        A = self.A_hat if A is None else normalize_adj(A)
        X = self._X if X is None else np.asarray(X, dtype=float)
        H1 = A @ X @ self.W1 + self.b1
        Z1 = np.maximum(0, H1)
        return (A @ Z1 @ self.W2 + self.b2).argmax(1)

    def fit_predict(self, A, X, y, train_mask):
        self.fit(A, X, y, train_mask)
        self._X = np.asarray(X, dtype=float)
        return self.predict()


def _softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def make_sbm(n_per=30, p_in=0.25, p_out=0.02, n_features=8, seed=0):
    """两个社区的随机块模型 + 社区相关特征。"""
    rng = np.random.default_rng(seed)
    n = 2 * n_per
    y = np.array([0] * n_per + [1] * n_per)
    A = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            p = p_in if y[i] == y[j] else p_out
            if rng.random() < p:
                A[i, j] = A[j, i] = 1
    X = rng.normal(0, 1, (n, n_features))
    X[y == 0, : n_features // 2] += 1.0
    X[y == 1, n_features // 2:] += 1.0
    return A, X, y


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
