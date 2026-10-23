"""变分自编码器 VAE — 手写实现（深度模型 · 生成式）

    vae = VAE(latent_dim=2, beta=1.0).fit(X)
    mu, logvar = vae.encode(X)
    samples = vae.sample(16)
    z = vae.interpolate(mu[0], mu[1], 10)

编码器输出分布参数 (mu, logvar)，重参数化采样 z，解码器重建。
损失 = MSE 重构 + beta * KL(q(z|x) || N(0,I))。
"""

from __future__ import annotations

import numpy as np


def sigmoid(z):
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


class VAE:
    def __init__(self, latent_dim: int = 2, lr: float = 1e-3, epochs: int = 100,
                 beta: float = 1.0, hidden: int = 32, random_state: int | None = 0) -> None:
        if latent_dim < 1 or hidden < 1:
            raise ValueError("latent_dim/hidden 必须 >=1")
        if beta < 0:
            raise ValueError("beta 不能为负")
        if epochs < 1:
            raise ValueError("epochs 必须 >=1")
        self.latent_dim = latent_dim
        self.lr = lr
        self.epochs = epochs
        self.beta = beta
        self.hidden = hidden
        self.random_state = random_state
        rng = np.random.default_rng(random_state)
        self.params = {
            "W1": rng.normal(0, np.sqrt(2 / 64), (64, hidden)),
            "b1": np.zeros(hidden),
            "Wmu": rng.normal(0, np.sqrt(2 / hidden), (hidden, latent_dim)),
            "bmu": np.zeros(latent_dim),
            "Wlv": rng.normal(0, np.sqrt(2 / hidden), (hidden, latent_dim)),
            "blv": np.zeros(latent_dim),
            "W2": rng.normal(0, np.sqrt(2 / latent_dim), (latent_dim, hidden)),
            "b2": np.zeros(hidden),
            "W3": rng.normal(0, np.sqrt(2 / hidden), (hidden, 64)),
            "b3": np.zeros(64),
        }
        self.loss_history: list[float] = []
        self.recon_history: list[float] = []
        self.kl_history: list[float] = []
        self._adam: dict[str, dict] = {}
        self._t = 0
        self.cache: dict = {}

    def _check_X(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != 64 or len(X) == 0:
            raise ValueError("X 应为非空 (N,64)")
        return X

    def _encode(self, X):
        h = np.maximum(X @ self.params["W1"] + self.params["b1"], 0)
        mu = h @ self.params["Wmu"] + self.params["bmu"]
        lv = h @ self.params["Wlv"] + self.params["blv"]
        return h, mu, lv

    def encode(self, X):
        X = self._check_X(X)
        _, mu, lv = self._encode(X)
        return mu, lv

    def reparameterize(self, mu, logvar, rng):
        eps = rng.normal(size=mu.shape)
        return mu + np.exp(0.5 * logvar) * eps

    def _decode(self, Z):
        h = np.maximum(Z @ self.params["W2"] + self.params["b2"], 0)
        return sigmoid(h @ self.params["W3"] + self.params["b3"]), h

    def decode(self, Z):
        Z = np.asarray(Z, dtype=float)
        if Z.ndim != 2 or Z.shape[1] != self.latent_dim:
            raise ValueError(f"Z 应为 (N,{self.latent_dim})")
        return self._decode(Z)[0]

    def reconstruct(self, X):
        X = self._check_X(X)
        _, mu, _ = self._encode(X)
        return self._decode(mu)[0]

    def _forward(self, X, rng):
        h, mu, lv = self._encode(X)
        eps = rng.normal(size=mu.shape)
        z = mu + np.exp(0.5 * lv) * eps
        xhat, h2 = self._decode(z)
        self.cache = {"X": X, "h": h, "mu": mu, "lv": lv, "eps": eps,
                      "z": z, "xhat": xhat, "h2": h2}
        return xhat

    def _backward(self):
        c = self.cache
        N, D = c["X"].shape
        # 重构项按“每个样本对像素求和、再对 batch 平均”，与 KL 的量级匹配
        dxhat = 2 * (c["xhat"] - c["X"]) / N
        dlogits = dxhat * c["xhat"] * (1 - c["xhat"])
        g = {}
        g["W3"] = c["h2"].T @ dlogits
        g["b3"] = dlogits.sum(0)
        dh2 = (dlogits @ self.params["W3"].T) * (c["h2"] > 0)
        g["W2"] = c["z"].T @ dh2
        g["b2"] = dh2.sum(0)
        dz = dh2 @ self.params["W2"].T
        # KL 的解析梯度（按 batch 平均）
        dmu = dz + self.beta * c["mu"] / N
        dlv = dz * 0.5 * np.exp(0.5 * c["lv"]) * c["eps"] \
            + self.beta * 0.5 * (np.exp(c["lv"]) - 1) / N
        g["Wmu"] = c["h"].T @ dmu
        g["bmu"] = dmu.sum(0)
        g["Wlv"] = c["h"].T @ dlv
        g["blv"] = dlv.sum(0)
        dh = (dmu @ self.params["Wmu"].T + dlv @ self.params["Wlv"].T) * (c["h"] > 0)
        g["W1"] = c["X"].T @ dh
        g["b1"] = dh.sum(0)
        return g

    def _step(self, grads):
        self._t += 1
        for k, p in self.params.items():
            g = grads[k]
            st = self._adam.setdefault(k, {"m": np.zeros_like(p), "v": np.zeros_like(p)})
            st["m"] = 0.9 * st["m"] + 0.1 * g
            st["v"] = 0.999 * st["v"] + 0.001 * g * g
            p -= self.lr * (st["m"] / (1 - 0.9 ** self._t)) / (
                np.sqrt(st["v"] / (1 - 0.999 ** self._t)) + 1e-8)

    def fit(self, X):
        X = self._check_X(X)
        rng = np.random.default_rng(self.random_state)
        self.loss_history, self.recon_history, self.kl_history = [], [], []
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            for s in range(0, len(X), 64):
                xb = X[order[s:s + 64]]
                self._forward(xb, rng)
                self._step(self._backward())
            # full-data 指标（不采样，使用 mu 重构；KL 用分布）
            mu, lv = self.encode(X)
            rec = float(np.mean(np.sum((self.decode(mu) - X) ** 2, axis=1)))
            kl = float(np.mean(-0.5 * np.sum(1 + lv - mu ** 2 - np.exp(lv), axis=1)))
            self.recon_history.append(rec)
            self.kl_history.append(kl)
            self.loss_history.append(rec + self.beta * kl)
        return self

    def sample(self, n=16):
        if n < 1:
            raise ValueError("n 必须 >=1")
        rng = np.random.default_rng(self.random_state)
        z = rng.normal(size=(n, self.latent_dim))
        return self._decode(z)[0]

    def interpolate(self, z1, z2, n=10):
        if n < 1:
            raise ValueError("n 必须 >=1")
        z1, z2 = np.asarray(z1, dtype=float), np.asarray(z2, dtype=float)
        if z1.shape != (self.latent_dim,) or z2.shape != (self.latent_dim,):
            raise ValueError(f"z1/z2 形状应为 ({self.latent_dim},)")
        alphas = np.linspace(0, 1, n)[:, None]
        return self.decode(z1 + alphas * (z2 - z1))


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
