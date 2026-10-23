"""多模态 CLIP 式 — 手写双塔 + 对称对比损失"""

from __future__ import annotations

import numpy as np


def l2norm(X):
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


def softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


class CLIP:
    def __init__(self, d=8, lr=0.1, epochs=100, tau=0.2, seed=0):
        if d < 1 or lr <= 0 or epochs < 1 or tau <= 0:
            raise ValueError("参数非法")
        self.d, self.lr, self.epochs, self.tau, self.seed = d, lr, epochs, tau, seed

    def fit(self, Xi, Xt):
        Xi = np.asarray(Xi, float)
        Xt = np.asarray(Xt, float)
        if Xi.ndim != 2 or Xt.ndim != 2 or len(Xi) != len(Xt):
            raise ValueError("Xi/Xt 形状不匹配")
        rng = np.random.default_rng(self.seed)
        self.Wi = rng.normal(0, 0.1, (Xi.shape[1], self.d))
        self.Wt = rng.normal(0, 0.1, (Xt.shape[1], self.d))
        self.loss_history = []
        n = len(Xi)
        for _ in range(self.epochs):
            zi, zt = Xi @ self.Wi, Xt @ self.Wt
            ni = np.maximum(np.linalg.norm(zi, axis=1, keepdims=True), 1e-12)
            nt = np.maximum(np.linalg.norm(zt, axis=1, keepdims=True), 1e-12)
            Ie, T = zi / ni, zt / nt
            logits = Ie @ T.T / self.tau
            P = softmax(logits)
            target = np.eye(n)
            loss = -0.5 * (np.mean(np.log(np.clip(np.diag(P), 1e-12, 1)))
                          + np.mean(np.log(np.clip(np.diag(P.T), 1e-12, 1))))
            self.loss_history.append(float(loss))
            G = (P - target) / n / self.tau
            dI = G @ T
            dT = G.T @ Ie
            # 反传 L2 归一化
            dI = (dI - Ie * (dI * Ie).sum(1, keepdims=True)) / ni
            dT = (dT - T * (dT * T).sum(1, keepdims=True)) / nt
            dWi = Xi.T @ dI
            dWt = Xt.T @ dT
            self.Wi -= self.lr * dWi
            self.Wt -= self.lr * dWt
        return self

    def embed(self, Xi, Xt):
        if not hasattr(self, "Wi"):
            raise RuntimeError("模型尚未训练")
        return l2norm(np.asarray(Xi) @ self.Wi), l2norm(np.asarray(Xt) @ self.Wt)

    def retrieval_accuracy(self, Xi, Xt, y=None):
        Ie, T = self.embed(Xi, Xt)
        logits = Ie @ T.T
        pred = logits.argmax(1)
        if y is None:
            return float((pred == np.arange(len(Ie))).mean())
        return float((np.asarray(y)[pred] == np.asarray(y)).mean())

    def similarity(self, Xi, Xt):
        Ie, T = self.embed(Xi, Xt)
        return Ie @ T.T


def make_pairs(n_per=20, dim_i=12, dim_t=200, seed=0):
    """每个类有固定的图像中心与文本 one-hot 词袋。"""
    rng = np.random.default_rng(seed)
    centers = rng.normal(0, 1, (10, dim_i))
    Xi, Xt, y = [], [], []
    for c in range(10):
        for _ in range(n_per):
            Xi.append(centers[c] + rng.normal(0, .25, dim_i))
            t = np.zeros(dim_t)
            t[len(Xt)] = 1.0
            t[c] += 0.5
            Xt.append(t)
            y.append(c)
    return np.array(Xi), np.array(Xt), np.array(y)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
