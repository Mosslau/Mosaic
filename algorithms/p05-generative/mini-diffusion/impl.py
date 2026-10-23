"""迷你扩散模型 DDPM — 手写实现（深度模型 · 生成式）

    ddpm = DDPM(n_steps=100, num_classes=10).train(X, y)
    xt = ddpm.q_sample(X0, t, noise)       # 前向闭式加噪
    samples = ddpm.sample(16)              # 无条件
    samples = ddpm.sample(16, labels, guidance=3.0)  # class-conditional + CFG

手写 MLP 去噪网络（时间嵌入 + 类别嵌入）；训练目标是预测加入的噪声 eps。
"""

from __future__ import annotations

import numpy as np


class Denoiser:
    """MLP：输入 [x_t, time_emb, class_emb] → 预测 eps。"""

    def __init__(self, num_classes=10, d_in=64, t_dim=16, c_dim=8, hidden=128,
                 random_state=0):
        rng = np.random.default_rng(random_state)
        self.num_classes = num_classes
        self.null = num_classes
        self.t_dim, self.c_dim = t_dim, c_dim
        self.class_emb = rng.normal(0, 0.02, (num_classes + 1, c_dim))
        self.W1 = rng.normal(0, np.sqrt(2 / (d_in + t_dim + c_dim)),
                             (d_in + t_dim + c_dim, hidden))
        self.b1 = np.zeros(hidden)
        self.W2 = rng.normal(0, np.sqrt(2 / hidden), (hidden, hidden))
        self.b2 = np.zeros(hidden)
        self.W3 = rng.normal(0, np.sqrt(2 / hidden), (hidden, d_in))
        self.b3 = np.zeros(d_in)
        self._init_grads()
        self.freq = np.exp(-np.log(10000.0) * np.arange(t_dim // 2) / (t_dim // 2))

    def _init_grads(self):
        for name in ("W1", "b1", "W2", "b2", "W3", "b3", "class_emb"):
            setattr(self, "d" + name, np.zeros_like(getattr(self, name)))

    def time_embed(self, t, n_steps=100):
        t = np.asarray(t, dtype=float) / n_steps
        args = t[:, None] * self.freq[None, :]
        return np.concatenate([np.sin(args), np.cos(args)], axis=1)

    def forward(self, x, t, y, n_steps=100):
        te = self.time_embed(t, n_steps)
        ce = self.class_emb[y]
        inp = np.concatenate([x, te, ce], axis=1)
        z1 = inp @ self.W1 + self.b1
        h1 = np.maximum(z1, 0)
        z2 = h1 @ self.W2 + self.b2
        h2 = np.maximum(z2, 0)
        out = h2 @ self.W3 + self.b3
        self.cache = {"inp": inp, "z1": z1, "h1": h1, "z2": z2, "h2": h2,
                      "y": y, "out": out}
        return out

    def backward(self, dout):
        c = self.cache
        self.dW3 = c["h2"].T @ dout
        self.db3 = dout.sum(0)
        dh2 = (dout @ self.W3.T) * (c["z2"] > 0)
        self.dW2 = c["h1"].T @ dh2
        self.db2 = dh2.sum(0)
        dh1 = (dh2 @ self.W2.T) * (c["z1"] > 0)
        self.dW1 = c["inp"].T @ dh1
        self.db1 = dh1.sum(0)
        dce = dh1 @ self.W1.T
        # 只取 class embedding 那一段
        dce = dce[:, 64 + self.t_dim:]
        self.dclass_emb = np.zeros_like(self.class_emb)
        np.add.at(self.dclass_emb, c["y"], dce)
        return None

    def params(self):
        return {"class_emb": self.class_emb, "W1": self.W1, "b1": self.b1,
                "W2": self.W2, "b2": self.b2, "W3": self.W3, "b3": self.b3}

    def grads(self):
        return {"class_emb": self.dclass_emb, "W1": self.dW1, "b1": self.db1,
                "W2": self.dW2, "b2": self.db2, "W3": self.dW3, "b3": self.db3}


class DDPM:
    def __init__(self, n_steps=100, lr=1e-3, epochs=100, beta_start=1e-4,
                 beta_end=0.1, num_classes=10, hidden=128, random_state=0):
        if n_steps < 2:
            raise ValueError("n_steps 必须 >=2")
        if epochs < 1 or hidden < 1:
            raise ValueError("epochs/hidden 必须 >=1")
        self.n_steps = n_steps
        self.lr = lr
        self.epochs = epochs
        self.beta_start, self.beta_end = beta_start, beta_end
        self.num_classes = num_classes
        self.random_state = random_state
        self.net = Denoiser(num_classes, hidden=hidden, random_state=random_state)
        self._build_schedule()
        self.loss_history: list[float] = []
        self._adam: dict[str, dict] = {}
        self._t = 0

    def _build_schedule(self):
        self.betas = np.linspace(self.beta_start, self.beta_end, self.n_steps)
        self.alphas = 1.0 - self.betas
        self.alphas_bar = np.cumprod(self.alphas)
        self.alphas_bar = np.clip(self.alphas_bar, 1e-8, 1.0)

    def q_sample(self, X_0, t, noise):
        X_0 = np.asarray(X_0, dtype=float)
        t = np.asarray(t, dtype=int)
        ab = self.alphas_bar[t][:, None]
        return np.sqrt(ab) * X_0 + np.sqrt(1 - ab) * noise

    def predict_noise(self, X_t, t, labels=None, guidance=1.0):
        if labels is None:
            y = np.full(len(X_t), self.net.null, dtype=int)
            return self.net.forward(X_t, t, y, self.n_steps)
        y = np.asarray(labels, dtype=int)
        if y.min() < 0 or y.max() >= self.num_classes:
            raise ValueError("labels 越界")
        if guidance < 0:
            raise ValueError("guidance 不能为负")
        if guidance == 1.0:
            return self.net.forward(X_t, t, y, self.n_steps)
        cond = self.net.forward(X_t, t, y, self.n_steps)
        uncond = self.net.forward(X_t, t, np.full(len(X_t), self.net.null), self.n_steps)
        return uncond + guidance * (cond - uncond)

    def train(self, X, y=None, batch_size=64):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != 64 or len(X) == 0:
            raise ValueError("X 应为非空 (N,64)")
        if y is None:
            y = np.full(len(X), self.net.null, dtype=int)
        y = np.asarray(y, dtype=int)
        if y.min() < 0 or y.max() >= self.net.num_classes:
            raise ValueError("y 越界")
        rng = np.random.default_rng(self.random_state)
        self.loss_history = []
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            total = 0.0
            for s in range(0, len(X), batch_size):
                idx = order[s:s + batch_size]
                xb, yb = X[idx], y[idx].copy()
                t = rng.integers(0, self.n_steps, size=len(xb))
                eps = rng.normal(size=xb.shape)
                xt = self.q_sample(xb, t, eps)
                # condition dropout：10% 置空，让模型同时学无条件
                drop = rng.random(len(xb)) < 0.1
                yb[drop] = self.net.null
                pred = self.net.forward(xt, t, yb, self.n_steps)
                loss = float(np.mean((pred - eps) ** 2))
                total += loss * len(xb)
                self.net.backward(2 * (pred - eps) / eps.size)
                self._step()
            self.loss_history.append(total / len(X))
        return self.loss_history

    def _step(self):
        self._t += 1
        for k, p in self.net.params().items():
            g = self.net.grads()[k]
            st = self._adam.setdefault(k, {"m": np.zeros_like(p), "v": np.zeros_like(p)})
            st["m"] = 0.9 * st["m"] + 0.1 * g
            st["v"] = 0.999 * st["v"] + 0.001 * g * g
            p -= self.lr * (st["m"] / (1 - 0.9 ** self._t)) / (
                np.sqrt(st["v"] / (1 - 0.999 ** self._t)) + 1e-8)

    def sample(self, n=16, labels=None, guidance=1.0, seed=0):
        if n < 1:
            raise ValueError("n 必须 >=1")
        if labels is not None:
            labels = np.asarray(labels, dtype=int)
            if labels.min() < 0 or labels.max() >= self.num_classes:
                raise ValueError("labels 越界")
        if guidance < 0:
            raise ValueError("guidance 不能为负")
        rng = np.random.default_rng(seed)
        x = rng.normal(size=(n, 64))
        for t in reversed(range(self.n_steps)):
            tt = np.full(n, t, dtype=int)
            eps = self.predict_noise(x, tt, labels, guidance)
            ab = self.alphas_bar[t]
            x0 = (x - np.sqrt(1 - ab) * eps) / np.sqrt(ab)
            x0 = np.clip(x0, 0, 1)
            if t == 0:
                x = x0
            else:
                ab_prev = self.alphas_bar[t - 1]
                mean = (np.sqrt(ab_prev) * self.betas[t] / (1 - ab) * x0
                        + np.sqrt(self.alphas[t]) * (1 - ab_prev) / (1 - ab) * x)
                var = self.betas[t] * (1 - ab_prev) / (1 - ab)
                x = mean + np.sqrt(var) * rng.normal(size=x.shape)
        return np.clip(x, 0, 1)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
