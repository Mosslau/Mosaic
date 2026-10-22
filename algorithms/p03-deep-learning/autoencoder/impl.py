"""AutoEncoder — 手写实现（深度模型 · 无监督）

无监督：没有 y，目标是重构输入自己。

    ae = AutoEncoder(latent_dim=2, denoising=0.0).fit(X_train)
    Z = ae.encode(X_test)               # 压缩表示
    X_hat = ae.reconstruct(X_test)
    err = ae.reconstruction_error(X_test)

结构：64 → 32 → latent → 32 → 64；隐层 ReLU，输出 sigmoid，损失 MSE。
`denoising>0` 时给输入加高斯噪声、目标仍是干净 X（denoising AE）。
"""

from __future__ import annotations

import numpy as np


def relu(z):
    return np.maximum(0.0, z)


def relu_grad(z):
    return (z > 0).astype(float)


def sigmoid(z):
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


class AutoEncoder:
    def __init__(self, latent_dim: int = 2, lr: float = 0.01, epochs: int = 100,
                 batch_size: int = 64, denoising: float = 0.0,
                 random_state: int | None = 0) -> None:
        if latent_dim < 1 or epochs < 1 or batch_size < 1:
            raise ValueError("latent_dim/epochs/batch_size 必须为正")
        if denoising < 0:
            raise ValueError("denoising 不能为负")
        self.latent_dim = latent_dim
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.denoising = denoising
        self.random_state = random_state
        self.params: dict = {}
        self.loss_history: list[float] = []
        self.param_history: list[dict] = []

    def _init_params(self, n_features, rng):
        H = 32
        self.params = {
            "W1": rng.normal(0, np.sqrt(2.0 / n_features), (n_features, H)),
            "b1": np.zeros(H),
            "W2": rng.normal(0, np.sqrt(2.0 / H), (H, self.latent_dim)),
            "b2": np.zeros(self.latent_dim),
            "W3": rng.normal(0, np.sqrt(2.0 / self.latent_dim), (self.latent_dim, H)),
            "b3": np.zeros(H),
            "W4": rng.normal(0, np.sqrt(2.0 / H), (H, n_features)),
            "b4": np.zeros(n_features),
        }

    def _forward(self, X, training=False):
        p = self.params
        z1 = X @ p["W1"] + p["b1"]
        a1 = relu(z1)
        z2 = a1 @ p["W2"] + p["b2"]
        z3 = z2 @ p["W3"] + p["b3"]
        a3 = relu(z3)
        logits = a3 @ p["W4"] + p["b4"]
        xhat = sigmoid(logits)
        return xhat, {"X": X, "z1": z1, "a1": a1, "z2": z2, "z3": z3, "a3": a3,
                      "logits": logits, "xhat": xhat}

    def encode(self, X):
        if not self.params:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        p = self.params
        a1 = relu(X @ p["W1"] + p["b1"])
        return a1 @ p["W2"] + p["b2"]

    def decode(self, Z):
        if not self.params:
            raise RuntimeError("模型尚未训练")
        Z = np.asarray(Z, dtype=float)
        p = self.params
        a3 = relu(Z @ p["W3"] + p["b3"])
        return sigmoid(a3 @ p["W4"] + p["b4"])

    def reconstruct(self, X):
        return self.decode(self.encode(X))

    def _backward(self, cache, X_target, n):
        p = self.params
        # MSE: dL/dxhat = 2(xhat - X)/n；sigmoid 导数
        dxhat = 2.0 * (cache["xhat"] - X_target) / n
        dlogits = dxhat * cache["xhat"] * (1 - cache["xhat"])
        grads = {}
        grads["W4"] = cache["a3"].T @ dlogits
        grads["b4"] = dlogits.sum(axis=0)
        da3 = dlogits @ p["W4"].T
        dz3 = da3 * relu_grad(cache["z3"])
        grads["W3"] = cache["z2"].T @ dz3
        grads["b3"] = dz3.sum(axis=0)
        dz2 = dz3 @ p["W3"].T
        grads["W2"] = cache["a1"].T @ dz2
        grads["b2"] = dz2.sum(axis=0)
        da1 = dz2 @ p["W2"].T
        dz1 = da1 * relu_grad(cache["z1"])
        grads["W1"] = cache["X"].T @ dz1
        grads["b1"] = dz1.sum(axis=0)
        return grads

    def _apply(self, grads, lr):
        self._t += 1
        for k, g in grads.items():
            st = self._adam.setdefault(k, {"m": np.zeros_like(g), "v": np.zeros_like(g)})
            st["m"] = 0.9 * st["m"] + 0.1 * g
            st["v"] = 0.999 * st["v"] + 0.001 * (g ** 2)
            mh = st["m"] / (1 - 0.9 ** self._t)
            vh = st["v"] / (1 - 0.999 ** self._t)
            self.params[k] -= lr * mh / (np.sqrt(vh) + 1e-8)

    def fit(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or len(X) == 0:
            raise ValueError("X 应为非空二维数组")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        rng = np.random.default_rng(self.random_state)
        self._init_params(X.shape[1], rng)
        self._adam = {}
        self._t = 0
        self.loss_history, self.param_history = [], []
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            for s in range(0, len(X), self.batch_size):
                idx = order[s:s + self.batch_size]
                clean = X[idx]
                noisy = clean
                if self.denoising > 0:
                    noisy = clean + rng.normal(0, self.denoising, size=clean.shape)
                xhat, cache = self._forward(noisy, training=True)
                grads = self._backward(cache, clean, clean.size)
                self._apply(grads, self.lr)
            xhat, _ = self._forward(X)
            self.loss_history.append(float(np.mean((xhat - X) ** 2)))
            self.param_history.append({k: v.copy() for k, v in self.params.items()})
        return self

    def reconstruction_error(self, X):
        X = np.asarray(X, dtype=float)
        return float(np.mean((self.reconstruct(X) - X) ** 2))


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
