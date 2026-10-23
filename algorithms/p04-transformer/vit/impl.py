"""ViT-lite — 手写 patch embedding + 单头自注意力 + 分类"""

from __future__ import annotations

import numpy as np


def softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


class ViT:
    def __init__(self, d=16, n_classes=10, lr=0.01, epochs=30, seed=0):
        if d < 1 or epochs < 1 or lr <= 0:
            raise ValueError("参数非法")
        self.d, self.n_classes, self.lr, self.epochs, self.seed = d, n_classes, lr, epochs, seed

    def fit(self, X, y):
        X = np.asarray(X, float)
        y = np.asarray(y)
        if X.ndim != 4 or X.shape[1:] != (1, 8, 8):
            raise ValueError("X 应为 (N,1,8,8)")
        rng = np.random.default_rng(self.seed)
        self.classes_ = np.unique(y)
        n = len(X)
        # 4 个 4x4 patch
        self.patches = X.reshape(n, 4, 16)
        self.cls = rng.normal(0, .1, (1, 1, self.d))
        self.E = rng.normal(0, np.sqrt(2 / 16), (16, self.d))
        self.pos = rng.normal(0, .05, (1, 5, self.d))
        self.Wq = rng.normal(0, np.sqrt(2 / self.d), (self.d, self.d))
        self.Wk = rng.normal(0, np.sqrt(2 / self.d), (self.d, self.d))
        self.Wv = rng.normal(0, np.sqrt(2 / self.d), (self.d, self.d))
        self.Wo = rng.normal(0, np.sqrt(2 / self.d), (self.d, self.d))
        self.W1 = rng.normal(0, np.sqrt(2 / self.d), (self.d, self.d * 2))
        self.b1 = np.zeros(self.d * 2)
        self.W2 = rng.normal(0, np.sqrt(2 / (self.d * 2)), (self.d * 2, self.d))
        self.b2 = np.zeros(self.d)
        self.Wc = rng.normal(0, np.sqrt(2 / self.d), (self.d, len(self.classes_)))
        self.bc = np.zeros(len(self.classes_))
        self.loss_history = []
        Y = np.eye(len(self.classes_))[np.searchsorted(self.classes_, y)]
        for _ in range(self.epochs):
            p = self.forward(n)
            loss = -np.mean(np.log(np.clip(p[np.arange(n), Y.argmax(1)], 1e-12, 1)))
            self.loss_history.append(float(loss))
            self.backward(p, Y)
        return self

    def _tokens(self, n):
        z = np.zeros((n, 5, self.d))
        z[:, :1] = self.cls
        z[:, 1:] = self.patches @ self.E
        return z + self.pos

    def forward(self, n=None):
        n = len(self.patches) if n is None else n
        self.Z0 = self._tokens(n)
        self.Q = self.Z0 @ self.Wq
        self.K = self.Z0 @ self.Wk
        self.V = self.Z0 @ self.Wv
        self.S = self.Q @ self.K.transpose(0, 2, 1) / np.sqrt(self.d)
        self.P = softmax(self.S)
        self.O = self.P @ self.V
        self.Z1 = self.Z0 + self.O @ self.Wo
        self.H = np.maximum(0, self.Z1 @ self.W1 + self.b1)
        self.Z2 = self.Z1 + self.H @ self.W2 + self.b2
        logits = self.Z2[:, 0] @ self.Wc + self.bc
        return softmax(logits)

    def backward(self, p, Y):
        n = len(p)
        dlogits = (p - Y) / n
        self.dWc = self.Z2[:, 0].T @ dlogits
        self.dbc = dlogits.sum(0)
        dZ2 = np.zeros_like(self.Z2)
        dZ2[:, 0] = dlogits @ self.Wc.T
        self.dW2 = self.H.reshape(-1, self.d * 2).T @ dZ2.reshape(-1, self.d)
        self.db2 = dZ2.sum((0, 1))
        dH = dZ2 @ self.W2.T
        dA = dH * (self.H > 0)
        self.dW1 = self.Z1.reshape(-1, self.d).T @ dA.reshape(-1, self.d * 2)
        self.db1 = dA.sum((0, 1))
        dZ1 = dZ2 + dA @ self.W1.T
        dO = dZ1 @ self.Wo.T
        self.dWo = self.O.reshape(-1, self.d).T @ dZ1.reshape(-1, self.d)
        # 逐样本 P@V 的反传
        dP = dO @ self.V.transpose(0, 2, 1)
        dV = self.P.transpose(0, 2, 1) @ dO
        dS = self.P * (dP - (dP * self.P).sum(-1, keepdims=True))
        dQ = dS @ self.K / np.sqrt(self.d)
        dK = dS.transpose(0, 2, 1) @ self.Q / np.sqrt(self.d)
        self.dWq = self.Z0.reshape(-1, self.d).T @ dQ.reshape(-1, self.d)
        self.dWk = self.Z0.reshape(-1, self.d).T @ dK.reshape(-1, self.d)
        self.dWv = self.Z0.reshape(-1, self.d).T @ dV.reshape(-1, self.d)
        dZ0 = dZ1 + dQ @ self.Wq.T + dK @ self.Wk.T + dV @ self.Wv.T
        self.dE = self.patches.reshape(-1, 16).T @ dZ0[:, 1:].reshape(-1, self.d)
        self.dpos = dZ0.sum(0, keepdims=True)
        self.dcls = dZ0[:, :1].sum(0, keepdims=True)
        self._step()

    def _step(self):
        for p, g in ((self.E, self.dE), (self.pos, self.dpos), (self.cls, self.dcls),
                     (self.Wq, self.dWq), (self.Wk, self.dWk), (self.Wv, self.dWv),
                     (self.Wo, self.dWo), (self.W1, self.dW1), (self.b1, self.db1),
                     (self.W2, self.dW2), (self.b2, self.db2), (self.Wc, self.dWc),
                     (self.bc, self.dbc)):
            p -= self.lr * g

    def predict_proba(self, X):
        if not hasattr(self, "patches"):
            raise RuntimeError("模型尚未训练")
        self.patches = np.asarray(X, float).reshape(len(X), 4, 16)
        p = self.forward()
        self.patches = None
        return p

    def predict(self, X):
        p = self.predict_proba(X)
        return self.classes_[p.argmax(1)]


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
