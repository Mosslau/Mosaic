"""条件 GAN：G/D 同时接类别 one-hot，目标提升 8×8 类别覆盖。"""

from __future__ import annotations

import numpy as np
from impl import _backward, _forward, bce


def _mlp(rng, sizes):
    return [{"W": rng.normal(0, np.sqrt(2 / a), (a, b)), "b": np.zeros(b)}
            for a, b in zip(sizes[:-1], sizes[1:])]


class ConditionalGAN:
    def __init__(self, latent_dim=16, n_classes=10, hidden=(64, 64),
                 lr_g=2e-4, lr_d=2e-4, epochs=300, seed=0):
        self.latent_dim, self.n_classes, self.hidden = latent_dim, n_classes, tuple(hidden)
        self.lr_g, self.lr_d, self.epochs, self.seed = lr_g, lr_d, epochs, seed

    def train(self, X, y, batch_size=64):
        X = np.asarray(X, float)
        y = np.asarray(y)
        if X.ndim != 2 or X.shape[1] != 64 or len(X) != len(y):
            raise ValueError("X 应为 (N,64)，y 一维")
        rng = np.random.default_rng(self.seed)
        self.G = _mlp(rng, [self.latent_dim + self.n_classes, *self.hidden, 64])
        self.D = _mlp(rng, [64 + self.n_classes, *self.hidden, 1])
        self._gs = [{"m": np.zeros_like(p["W"]), "v": np.zeros_like(p["W"])} for p in self.G]
        self._ds = [{"m": np.zeros_like(p["W"]), "v": np.zeros_like(p["W"])} for p in self.D]
        self._t = 0
        self.d_loss, self.g_loss = [], []
        Y = np.eye(self.n_classes)[y]
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            for s in range(0, len(X), batch_size):
                idx = order[s:s + batch_size]
                xb, yb = X[idx], Y[idx]
                n = len(idx)
                z = rng.normal(0, 1, (n, self.latent_dim))
                gin = np.c_[z, yb]
                fake, gc = _forward(self.G, gin, True)
                real_in = np.c_[xb, yb]
                fake_in = np.c_[fake, yb]
                pr, cr = _forward(self.D, real_in, True)
                pf, cf = _forward(self.D, fake_in, True)
                self.d_loss.append(bce(pr, 1.0) + bce(pf, 0.0))
                gr, _ = _backward(self.D, cr, ((pr - 1) / n), True)
                gf, _ = _backward(self.D, cf, (pf / n), True)
                gd = [{"W": a["W"] + b["W"], "b": a["b"] + b["b"]} for a, b in zip(gr, gf)]
                self._adam(self.D, gd, self._ds, self.lr_d)
                # G：只回传 D 的输入梯度，不更新 D
                fake2, gc2 = _forward(self.G, gin, True)
                pf2, cf2 = _forward(self.D, np.c_[fake2, yb], True)
                self.g_loss.append(bce(pf2, 1.0))
                _, din = _backward(self.D, cf2, (-(1 - pf2) / n), True)
                dfake = din[:, :64]
                gg, _ = _backward(self.G, gc2, dfake, True)
                self._adam(self.G, gg, self._gs, self.lr_g)
        return self

    def _adam(self, params, grads, state, lr):
        self._t += 1
        for p, g, st in zip(params, grads, state):
            st["m"] = 0.9 * st["m"] + 0.1 * g["W"]
            st["v"] = 0.999 * st["v"] + 0.001 * g["W"] ** 2
            mh = st["m"] / (1 - 0.9 ** self._t)
            vh = st["v"] / (1 - 0.999 ** self._t)
            p["W"] -= lr * mh / (np.sqrt(vh) + 1e-8)
            p["b"] -= lr * g["b"]

    def sample(self, n=256, labels=None, seed=0):
        if not hasattr(self, "G"):
            raise RuntimeError("模型尚未训练")
        rng = np.random.default_rng(seed)
        if labels is None:
            labels = rng.integers(self.n_classes, size=n)
        labels = np.asarray(labels, int)
        z = rng.normal(0, 1, (n, self.latent_dim))
        out, _ = _forward(self.G, np.c_[z, np.eye(self.n_classes)[labels]], True)
        return out


if __name__ == "__main__":
    raise SystemExit("本文件是库，实验入口由 demo/test 调用")
