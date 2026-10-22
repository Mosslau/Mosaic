"""GAN — 手写实现（深度模型 · 生成式）

两个 MLP 交替对抗：生成器 G: z→x，判别器 D: x→[0,1]。
支持原始 saturating 损失与常用的 **non-saturating** 损失（-log D(G(z))）。

    gan = GAN(latent_dim=8, loss_type="non_saturating").train(X, epochs=200)
    samples = gan.sample(500)
    modes = mode_coverage(samples, centers)
"""

from __future__ import annotations

import numpy as np


def leaky_relu(z, alpha=0.01):
    return np.where(z > 0, z, alpha * z)


def leaky_relu_grad(z, alpha=0.01):
    return np.where(z > 0, 1.0, alpha)


def sigmoid(z):
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def _forward(params, X, out_sigmoid=False):
    A = np.asarray(X, dtype=float)
    caches = []
    for i, p in enumerate(params):
        A_prev = A
        Z = A_prev @ p["W"] + p["b"]
        last = i == len(params) - 1
        A = sigmoid(Z) if (last and out_sigmoid) else (Z if last else leaky_relu(Z))
        caches.append({"A_prev": A_prev, "Z": Z, "A": A, "last": last})
    return A, caches


def _backward(params, caches, dout, out_sigmoid=False):
    grads = [dict() for _ in params]
    dA = dout
    for i in range(len(params) - 1, -1, -1):
        c = caches[i]
        if c["last"]:
            dZ = dA * (c["A"] * (1 - c["A"]) if out_sigmoid else 1.0)
        else:
            dZ = dA * leaky_relu_grad(c["Z"])
        grads[i]["W"] = c["A_prev"].T @ dZ
        grads[i]["b"] = dZ.sum(axis=0)
        dA = dZ @ params[i]["W"].T
    return grads, dA


def bce(p, target):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(target * np.log(p) + (1 - target) * np.log(1 - p)))


def mode_coverage(samples, centers, threshold=0.35):
    """把生成样本分给最近的中心（距离 < threshold），返回覆盖数/熵/多样性。"""
    d = np.linalg.norm(samples[:, None, :] - centers[None, :, :], axis=2)
    idx = d.argmin(axis=1)
    close = d.min(axis=1) < threshold
    counts = np.bincount(idx[close], minlength=len(centers)).astype(float)
    covered = int(np.sum(counts > 0))
    probs = counts / max(counts.sum(), 1)
    ent = float(-np.sum(probs[probs > 0] * np.log(probs[probs > 0])))
    dists = np.linalg.norm(samples[:, None, :] - samples[None, :, :], axis=2)
    nn = float(np.mean(np.partition(dists, 2, axis=1)[:, 1]))
    return {"covered": covered, "n_modes": len(centers), "entropy": ent,
            "nn_distance": nn, "counts": counts.astype(int)}


class GAN:
    def __init__(self, data_dim: int = 2, latent_dim: int = 8,
                 hidden: tuple[int, ...] = (64, 64), lr_g: float = 2e-4,
                 lr_d: float = 2e-4, loss_type: str = "non_saturating",
                 out_sigmoid: bool = False, g_steps: int = 1,
                 random_state: int | None = 0) -> None:
        if loss_type not in ("non_saturating", "saturating"):
            raise ValueError("loss_type 只支持 non_saturating / saturating")
        self.data_dim = data_dim
        self.latent_dim = latent_dim
        self.hidden = tuple(hidden)
        self.lr_g = lr_g
        self.lr_d = lr_d
        self.loss_type = loss_type
        self.out_sigmoid = out_sigmoid
        self.g_steps = int(g_steps)
        self.random_state = random_state
        self.g_params: list[dict] = []
        self.d_params: list[dict] = []
        self.d_loss_history: list[float] = []
        self.g_loss_history: list[float] = []
        self.d_acc_history: list[float] = []
        self.sample_history: list[np.ndarray] = []

    def _init(self, rng):
        def mlp(sizes):
            return [{"W": rng.normal(0, np.sqrt(2.0 / a), (a, b)), "b": np.zeros(b)}
                    for a, b in zip(sizes[:-1], sizes[1:])]
        self.g_params = mlp([self.latent_dim, *self.hidden, self.data_dim])
        self.d_params = mlp([self.data_dim, *self.hidden, 1])
        self._g_state = [{"m": np.zeros_like(p["W"]), "v": np.zeros_like(p["W"])}
                         for p in self.g_params]
        self._d_state = [{"m": np.zeros_like(p["W"]), "v": np.zeros_like(p["W"])}
                         for p in self.d_params]
        self._t = 0

    def generator(self, Z):
        if not self.g_params:
            raise RuntimeError("模型尚未训练")
        out, _ = _forward(self.g_params, Z, self.out_sigmoid)
        return out

    def discriminator(self, X):
        if not self.d_params:
            raise RuntimeError("模型尚未训练")
        out, _ = _forward(self.d_params, X, True)
        return out.ravel()

    def _adam(self, params, grads, state, lr):
        self._t += 1
        for p, g, st in zip(params, grads, state):
            st["m"] = 0.9 * st["m"] + 0.1 * g["W"]
            st["v"] = 0.999 * st["v"] + 0.001 * (g["W"] ** 2)
            mh = st["m"] / (1 - 0.9 ** self._t)
            vh = st["v"] / (1 - 0.999 ** self._t)
            p["W"] -= lr * mh / (np.sqrt(vh) + 1e-8)
            p["b"] -= lr * g["b"]

    def train(self, X, epochs=200, batch_size=64):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or len(X) < 2:
            raise ValueError("X 应为至少 2 行的二维数组")
        rng = np.random.default_rng(self.random_state)
        self._init(rng)
        self.d_loss_history, self.g_loss_history, self.d_acc_history = [], [], []
        self.sample_history = []
        n = len(X)
        for _ in range(epochs):
            order = rng.permutation(n)
            for s in range(0, n, batch_size):
                real = X[order[s:s + batch_size]]
                m = len(real)
                z = rng.normal(size=(m, self.latent_dim))
                fake = self.generator(z)

                d_real = self.discriminator(real)
                d_fake = self.discriminator(fake)
                d_loss = bce(d_real, np.ones(m)) + bce(d_fake, np.zeros(m))
                gD_real, _ = _backward(self.d_params, _forward(self.d_params, real, True)[1],
                                       ((d_real - 1) / m)[:, None], True)
                gD_fake, _ = _backward(self.d_params, _forward(self.d_params, fake, True)[1],
                                       (d_fake / m)[:, None], True)
                gradsD = [{"W": a["W"] + b["W"], "b": a["b"] + b["b"]}
                          for a, b in zip(gD_real, gD_fake)]
                self._adam(self.d_params, gradsD, self._d_state, self.lr_d)

                # G：冻结 D，只回传到 G；可多次更新
                for _ in range(self.g_steps):
                    fake = self.generator(z)
                    d_out, cache_d = _forward(self.d_params, fake, True)
                    d_out = d_out.ravel()
                    if self.loss_type == "non_saturating":
                        g_loss = float(-np.mean(np.log(np.clip(d_out, 1e-12, 1))))
                        dlogits = (-1.0 / (np.clip(d_out, 1e-12, 1) * m))[:, None]
                    else:
                        g_loss = float(np.mean(np.log(np.clip(1 - d_out, 1e-12, 1))))
                        dlogits = (-1.0 / (np.clip(1 - d_out, 1e-12, 1) * m))[:, None]
                    _, d_fake_dx = _backward(self.d_params, cache_d, dlogits, True)
                    _, cache_g = _forward(self.g_params, z, self.out_sigmoid)
                    gradsG, _ = _backward(self.g_params, cache_g, d_fake_dx, self.out_sigmoid)
                    self._adam(self.g_params, gradsG, self._g_state, self.lr_g)

            self.d_loss_history.append(d_loss)
            self.g_loss_history.append(g_loss)
            self.d_acc_history.append(float((np.mean(d_real > 0.5) + np.mean(d_fake < 0.5)) / 2))
            if len(self.d_loss_history) % 10 == 0:
                self.sample_history.append(self.sample(256))
        return self

    def sample(self, n=16):
        rng = np.random.default_rng(self.random_state)
        z = rng.normal(size=(n, self.latent_dim))
        return self.generator(z)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
