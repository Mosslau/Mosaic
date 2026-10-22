"""RNN 与 LSTM — 手写实现（深度模型 · 判别式）

序列分类：输入 `(N, T, input_size)`，输出 `(N, n_classes)`。
手写沿时间反向传播（BPTT）、梯度裁剪、Adam，并支持“不同 T 下的梯度范数”诊断。

    rnn = RNN(input_size=2, hidden_size=32, n_classes=2).fit(X, y)
    proba = rnn.predict_proba(X)
    gn = rnn.grad_norm_for_T(X_long, y_long)   # 观察梯度随 T 衰减/爆炸
"""

from __future__ import annotations

import numpy as np


def sigmoid(z: np.ndarray) -> np.ndarray:
    """数值稳定 sigmoid：正负分支避免 exp 溢出。"""
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class _RecurrentBase:
    def __init__(self, input_size: int = 2, hidden_size: int = 32,
                 n_classes: int = 2, lr: float = 0.01, epochs: int = 30,
                 batch_size: int = 32, clip_norm: float | None = 1.0,
                 random_state: int | None = 0) -> None:
        if hidden_size < 1 or epochs < 1 or batch_size < 1:
            raise ValueError("hidden_size/epochs/batch_size 必须为正")
        if clip_norm is not None and clip_norm <= 0:
            raise ValueError("clip_norm 必须为正或 None")
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.n_classes = n_classes
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.clip_norm = clip_norm
        self.random_state = random_state
        self.params: dict = {}
        self.loss_history: list[float] = []
        self.grad_norm_history: list[float] = []
        self.classes_ = None

    # -- 参数初始化交给子类（LSTM 的 Wx/Wh 是 4 倍宽）
    def _init_params(self, rng):  # pragma: no cover - 子类实现
        raise NotImplementedError

    def forward(self, X, training=False):  # pragma: no cover
        raise NotImplementedError

    def backward(self, proba, y_onehot, cache):  # pragma: no cover
        raise NotImplementedError

    # ------------------------------------------------------------------ 训练

    def _clip(self, grads: dict) -> tuple[dict, float]:
        norm = float(np.sqrt(sum(np.sum(g ** 2) for g in grads.values())))
        if self.clip_norm is not None and norm > self.clip_norm:
            scale = self.clip_norm / (norm + 1e-12)
            grads = {k: g * scale for k, g in grads.items()}
        return grads, norm

    def _adam_step(self, grads: dict, lr: float) -> None:
        self._t += 1
        for k, g in grads.items():
            st = self._adam.setdefault(k, {"m": np.zeros_like(g), "v": np.zeros_like(g)})
            st["m"] = 0.9 * st["m"] + 0.1 * g
            st["v"] = 0.999 * st["v"] + 0.001 * (g ** 2)
            mh = st["m"] / (1 - 0.9 ** self._t)
            vh = st["v"] / (1 - 0.999 ** self._t)
            self.params[k] -= lr * mh / (np.sqrt(vh) + 1e-8)

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 3 or y.ndim != 1 or len(X) != len(y):
            raise ValueError("X 应为 (N,T,input_size)，y 为一维")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        if self.n_classes < 2:
            raise ValueError("n_classes 至少为 2")
        self.classes_, yi = np.unique(y, return_inverse=True)
        if len(self.classes_) != self.n_classes:
            raise ValueError("y 的类别数与 n_classes 不一致")
        y1 = np.eye(self.n_classes)[yi]
        rng = np.random.default_rng(self.random_state)
        self._init_params(rng)
        self._adam = {}
        self._t = 0
        self.loss_history, self.grad_norm_history = [], []
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            norms = []
            for s in range(0, len(X), self.batch_size):
                idx = order[s:s + self.batch_size]
                proba, cache = self.forward(X[idx], training=True)
                grads = self.backward(proba, y1[idx], cache)
                grads, norm = self._clip(grads)
                norms.append(norm)
                self._adam_step(grads, self.lr)
            p, _ = self.forward(X, training=False)
            self.loss_history.append(float(-np.mean(np.log(np.clip(
                p[np.arange(len(X)), yi], 1e-12, 1)))))
            self.grad_norm_history.append(float(np.mean(norms)))
        return self

    def predict_proba(self, X):
        if not self.params:
            raise RuntimeError("模型尚未训练")
        p, _ = self.forward(np.asarray(X, dtype=float), training=False)
        return p

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]

    def grad_norm_h0_for_T(self, X, y) -> float:
        """梯度范数（对初始隐状态 h0）——直接衡量“T 步之后还能传回多少信用”。"""
        if not self.params:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        classes = list(self.classes_)
        yi = np.array([classes.index(v) for v in y])
        proba, cache = self.forward(X, training=False)
        self.backward(proba, np.eye(self.n_classes)[yi], cache)
        return self.h0_grad_norm

    def grad_norm_for_T(self, X, y) -> float:
        """给定一批序列，返回**未裁剪**的全局梯度范数（诊断梯度消失/爆炸）。"""
        if not self.params:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        classes = list(self.classes_)
        yi = np.array([classes.index(v) for v in y])
        proba, cache = self.forward(X, training=False)
        grads = self.backward(proba, np.eye(self.n_classes)[yi], cache)
        return float(np.sqrt(sum(np.sum(g ** 2) for g in grads.values())))


class RNN(_RecurrentBase):
    """朴素 RNN：h_t = tanh(x_t W_x + h_{t-1} W_h + b)。"""

    def _init_params(self, rng):
        H, D = self.hidden_size, self.input_size
        self.params = {
            "Wx": rng.normal(0, np.sqrt(1.0 / D), (D, H)),
            "Wh": rng.normal(0, np.sqrt(1.0 / H), (H, H)),
            "bh": np.zeros(H),
            "Wy": rng.normal(0, np.sqrt(1.0 / H), (H, self.n_classes)),
            "by": np.zeros(self.n_classes),
        }

    def forward(self, X, training=False):
        N, T, _ = X.shape
        h = np.zeros((N, self.hidden_size))
        hs = [h]
        for t in range(T):
            h = np.tanh(X[:, t] @ self.params["Wx"] + h @ self.params["Wh"]
                        + self.params["bh"])
            hs.append(h)
        logits = hs[-1] @ self.params["Wy"] + self.params["by"]
        return _softmax(logits), {"hs": hs, "X": X}

    def backward(self, proba, y_onehot, cache):
        hs, X = cache["hs"], cache["X"]
        N, T, _ = X.shape
        dlogits = (proba - y_onehot) / N
        dWy = hs[-1].T @ dlogits
        dby = dlogits.sum(axis=0)
        dh = dlogits @ self.params["Wy"].T
        grads = {k: np.zeros_like(v) for k, v in self.params.items()}
        grads["Wy"], grads["by"] = dWy, dby
        for t in range(T - 1, -1, -1):
            dz = dh * (1 - hs[t + 1] ** 2)
            grads["Wx"] += X[:, t].T @ dz
            grads["Wh"] += hs[t].T @ dz
            grads["bh"] += dz.sum(axis=0)
            dh = dz @ self.params["Wh"].T
        self.h0_grad_norm = float(np.linalg.norm(dh))
        return grads


class LSTM(_RecurrentBase):
    """LSTM：i/f/o/g 四组门，c_t = f⊙c_{t-1} + i⊙g，h_t = o⊙tanh(c_t)。"""

    def _init_params(self, rng):
        H, D = self.hidden_size, self.input_size
        self.params = {
            "Wx": rng.normal(0, np.sqrt(1.0 / D), (D, 4 * H)),
            "Wh": rng.normal(0, np.sqrt(1.0 / H), (H, 4 * H)),
            "b": np.zeros(4 * H),
            "Wy": rng.normal(0, np.sqrt(1.0 / H), (H, self.n_classes)),
            "by": np.zeros(self.n_classes),
        }

    def forward(self, X, training=False):
        N, T, _ = X.shape
        H = self.hidden_size
        h = np.zeros((N, H))
        c = np.zeros((N, H))
        cache = []
        for t in range(T):
            z = X[:, t] @ self.params["Wx"] + h @ self.params["Wh"] + self.params["b"]
            i = sigmoid(z[:, :H])
            f = sigmoid(z[:, H:2 * H])
            o = sigmoid(z[:, 2 * H:3 * H])
            g = np.tanh(z[:, 3 * H:])
            c_prev = c
            c = f * c_prev + i * g
            tc = np.tanh(c)
            h = o * tc
            cache.append({"x": X[:, t], "h_prev": cache[-1]["h"] if cache else np.zeros((N, H)),
                          "c_prev": c_prev, "i": i, "f": f, "o": o, "g": g,
                          "tc": tc, "h": h})
        logits = h @ self.params["Wy"] + self.params["by"]
        return _softmax(logits), {"cache": cache, "hT": h}

    def backward(self, proba, y_onehot, cache):
        cs = cache["cache"]
        N, T = len(y_onehot), len(cs)
        H = self.hidden_size
        dlogits = (proba - y_onehot) / N
        dWy = cache["hT"].T @ dlogits
        dby = dlogits.sum(axis=0)
        dh = dlogits @ self.params["Wy"].T
        dc = np.zeros((N, H))
        grads = {k: np.zeros_like(v) for k, v in self.params.items()}
        grads["Wy"], grads["by"] = dWy, dby
        for t in range(T - 1, -1, -1):
            c = cs[t]
            do = dh * c["tc"]
            dc = dc + dh * c["o"] * (1 - c["tc"] ** 2)
            di = dc * c["g"]
            dg = dc * c["i"]
            df = dc * c["c_prev"]
            dc_prev = dc * c["f"]
            dz_i = di * c["i"] * (1 - c["i"])
            dz_f = df * c["f"] * (1 - c["f"])
            dz_o = do * c["o"] * (1 - c["o"])
            dz_g = dg * (1 - c["g"] ** 2)
            dz = np.concatenate([dz_i, dz_f, dz_o, dz_g], axis=1)
            grads["Wx"] += c["x"].T @ dz
            grads["Wh"] += c["h_prev"].T @ dz
            grads["b"] += dz.sum(axis=0)
            dh = dz @ self.params["Wh"].T
            dc = dc_prev
        self.h0_grad_norm = float(np.sqrt(np.linalg.norm(dh) ** 2
                                          + np.linalg.norm(dc) ** 2))
        return grads


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
