"""MLP 与手写反向传播 — 手写实现（深度模型 · 判别式）

本仓库**最重要的一篇手写实验**：后面 CNN / RNN / Transformer 的反向传播都是
这里那套链式法则的复用。用 numpy 手写前向缓存、反向梯度、优化器、初始化、
dropout / weight decay、LR schedule 与 early stopping。

    mlp = MLP(hidden_sizes=(64, 32), lr=0.01, epochs=30,
              optimizer="adam", init="he").fit(X_train, y_train)
    proba = mlp.predict_proba(X_test)
    label = mlp.predict(X_test)
"""

from __future__ import annotations

import numpy as np


def relu(z: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, z)


def relu_grad(z: np.ndarray) -> np.ndarray:
    """ReLU 导数：z > 0 处为 1，否则 0（z=0 的次梯度取 0）。"""
    return (z > 0).astype(float)


def softmax(z: np.ndarray) -> np.ndarray:
    """数值稳定 softmax：先减每行最大值。"""
    z = np.asarray(z, dtype=float)
    shifted = z - z.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def _one_hot(y: np.ndarray, k: int) -> np.ndarray:
    out = np.zeros((len(y), k))
    out[np.arange(len(y)), y] = 1.0
    return out


class MLP:
    """多层感知机：任意隐层，交叉熵 + 手写反向传播。"""

    def __init__(
        self,
        hidden_sizes: tuple[int, ...] = (64, 32),
        lr: float = 0.01,
        epochs: int = 30,
        batch_size: int = 32,
        optimizer: str = "sgd",
        init: str = "he",
        weight_decay: float = 0.0,
        dropout: float = 0.0,
        lr_schedule: str = "none",
        lr_decay: float = 0.5,
        step_size: int = 10,
        early_stopping: bool = False,
        patience: int = 5,
        validation_split: float = 0.0,
        momentum: float = 0.9,
        random_state: int | None = None,
    ) -> None:
        if not hidden_sizes or any(h < 1 for h in hidden_sizes):
            raise ValueError("hidden_sizes 必须是非空的正整数元组")
        if lr <= 0 or epochs < 1 or batch_size < 1:
            raise ValueError("lr/epochs/batch_size 必须为正")
        if optimizer not in ("sgd", "momentum", "adam"):
            raise ValueError("optimizer 只支持 sgd / momentum / adam")
        if init not in ("he", "xavier", "zero", "random"):
            raise ValueError("init 只支持 he / xavier / zero / random")
        if not (0.0 <= dropout < 1.0):
            raise ValueError("dropout 必须在 [0,1) 内")
        if weight_decay < 0:
            raise ValueError("weight_decay 不能为负")
        if lr_schedule not in ("none", "step", "cosine"):
            raise ValueError("lr_schedule 只支持 none / step / cosine")
        if not (0.0 <= validation_split < 1.0):
            raise ValueError("validation_split 必须在 [0,1) 内")
        self.hidden_sizes = tuple(hidden_sizes)
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.batch_size = int(batch_size)
        self.optimizer = optimizer
        self.init = init
        self.weight_decay = float(weight_decay)
        self.dropout = float(dropout)
        self.lr_schedule = lr_schedule
        self.lr_decay = float(lr_decay)
        self.step_size = int(step_size)
        self.early_stopping = bool(early_stopping)
        self.patience = int(patience)
        self.validation_split = float(validation_split)
        self.momentum = float(momentum)
        self.random_state = random_state
        self.params: list[dict] = []
        self.loss_history: list[float] = []
        self.val_loss_history: list[float] = []
        self.param_history: list[list[dict]] = []
        self.epochs_run = 0
        self.current_lr_ = self.lr
        self.classes_: np.ndarray | None = None
        self._rng = np.random.default_rng(random_state)
        self._state: list[dict] = []

    # ------------------------------------------------------------------ 初始化

    def _init_params(self, n_features: int, n_classes: int) -> None:
        sizes = [n_features, *self.hidden_sizes, n_classes]
        self.params = []
        for i, (fan_in, fan_out) in enumerate(zip(sizes[:-1], sizes[1:])):
            if self.init == "zero":
                W = np.zeros((fan_in, fan_out))
            elif self.init == "random":
                W = self._rng.normal(0.0, 0.01, size=(fan_in, fan_out))
            elif self.init == "xavier":
                limit = np.sqrt(6.0 / (fan_in + fan_out))
                W = self._rng.uniform(-limit, limit, size=(fan_in, fan_out))
            else:  # he
                W = self._rng.normal(0.0, np.sqrt(2.0 / fan_in), size=(fan_in, fan_out))
            self.params.append({"W": W, "b": np.zeros(fan_out)})
        self._state = [
            {"vW": np.zeros_like(p["W"]), "vb": np.zeros_like(p["b"]),
             "mW": np.zeros_like(p["W"]), "mb": np.zeros_like(p["b"])}
            for p in self.params
        ]
        self._t = 0

    # ------------------------------------------------------------------ 前向/反向

    def forward(self, X: np.ndarray, training: bool = False) -> tuple[np.ndarray, list[dict]]:
        A = np.asarray(X, dtype=float)
        caches: list[dict] = []
        for i, p in enumerate(self.params[:-1]):
            A_prev = A
            Z = A_prev @ p["W"] + p["b"]
            A = relu(Z)
            mask = None
            if training and self.dropout > 0:
                mask = (self._rng.random(A.shape) >= self.dropout) / (1.0 - self.dropout)
                A = A * mask
            caches.append({"A_prev": A_prev, "Z": Z, "mask": mask})
        p = self.params[-1]
        A_prev = A
        Z = A_prev @ p["W"] + p["b"]
        proba = softmax(Z)
        caches.append({"A_prev": A_prev, "Z": Z, "mask": None})
        return proba, caches

    def backward(self, cache: list[dict], y_onehot: np.ndarray) -> list[dict]:
        grads: list[dict | None] = [None] * len(self.params)
        n = len(y_onehot)
        # softmax + 交叉熵：dZ = (proba − y)/n
        dZ = (softmax(cache[-1]["Z"]) - y_onehot) / n
        for layer in range(len(self.params) - 1, -1, -1):
            c = cache[layer]
            dW = c["A_prev"].T @ dZ + self.weight_decay * self.params[layer]["W"]
            db = dZ.sum(axis=0)
            grads[layer] = {"W": dW, "b": db}
            if layer > 0:
                dA = dZ @ self.params[layer]["W"].T
                prev = cache[layer - 1]
                dZ = dA * relu_grad(prev["Z"])
                if prev["mask"] is not None:
                    dZ *= prev["mask"]
        return grads  # type: ignore[return-value]

    # ------------------------------------------------------------------ 优化器

    def _update(self, grads: list[dict], lr: float) -> None:
        self._t += 1
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        for layer, p in enumerate(self.params):
            gW, gb = grads[layer]["W"], grads[layer]["b"]
            s = self._state[layer]
            if self.optimizer == "sgd":
                p["W"] -= lr * gW
                p["b"] -= lr * gb
            elif self.optimizer == "momentum":
                s["vW"] = self.momentum * s["vW"] - lr * gW
                s["vb"] = self.momentum * s["vb"] - lr * gb
                p["W"] += s["vW"]
                p["b"] += s["vb"]
            else:  # adam
                s["mW"] = beta1 * s["mW"] + (1 - beta1) * gW
                s["mb"] = beta1 * s["mb"] + (1 - beta1) * gb
                s["vW"] = beta2 * s["vW"] + (1 - beta2) * (gW ** 2)
                s["vb"] = beta2 * s["vb"] + (1 - beta2) * (gb ** 2)
                mhat = s["mW"] / (1 - beta1 ** self._t)
                vhat = s["vW"] / (1 - beta2 ** self._t)
                p["W"] -= lr * mhat / (np.sqrt(vhat) + eps)
                mhat_b = s["mb"] / (1 - beta1 ** self._t)
                vhat_b = s["vb"] / (1 - beta2 ** self._t)
                p["b"] -= lr * mhat_b / (np.sqrt(vhat_b) + eps)

    def _lr_for_epoch(self, epoch: int) -> float:
        if self.lr_schedule == "step":
            return self.lr * self.lr_decay ** (epoch // max(self.step_size, 1))
        if self.lr_schedule == "cosine":
            return 0.5 * self.lr * (1.0 + np.cos(np.pi * epoch / self.epochs))
        return self.lr

    # ------------------------------------------------------------------ 训练

    def _loss(self, X: np.ndarray, y_onehot: np.ndarray) -> float:
        proba, _ = self.forward(X, training=False)
        return float(-np.mean(np.sum(y_onehot * np.log(np.clip(proba, 1e-12, 1.0)), axis=1)))

    def fit(self, X: np.ndarray, y: np.ndarray) -> MLP:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 2 or y.ndim != 1 or len(X) != len(y):
            raise ValueError("X / y 形状不匹配")
        if len(X) == 0:
            raise ValueError("样本数为 0")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        self.classes_, y_idx = np.unique(y, return_inverse=True)
        n_classes = len(self.classes_)
        y_onehot = _one_hot(y_idx, n_classes)

        X_fit, y_fit, X_val, y_val = X, y_onehot, None, None
        if self.validation_split > 0:
            n_val = max(1, int(len(X) * self.validation_split))
            idx = self._rng.permutation(len(X))
            val_idx, train_idx = idx[:n_val], idx[n_val:]
            X_fit, y_fit = X[train_idx], y_onehot[train_idx]
            X_val, y_val = X[val_idx], y_onehot[val_idx]

        self._init_params(X.shape[1], n_classes)
        self.loss_history, self.val_loss_history = [], []
        self.param_history = []
        self.epochs_run = 0
        best_loss, best_params, wait = np.inf, None, 0

        for epoch in range(self.epochs):
            lr = self._lr_for_epoch(epoch)
            self.current_lr_ = lr
            order = self._rng.permutation(len(X_fit))
            for start in range(0, len(X_fit), self.batch_size):
                idx = order[start:start + self.batch_size]
                _, cache = self.forward(X_fit[idx], training=True)
                grads = self.backward(cache, y_fit[idx])
                self._update(grads, lr)
            train_loss = self._loss(X_fit, y_fit)
            self.loss_history.append(train_loss)
            if X_val is not None:
                val_loss = self._loss(X_val, y_val)
                self.val_loss_history.append(val_loss)
                monitor = val_loss
            else:
                monitor = train_loss
            self.epochs_run += 1
            self.param_history.append(
                [{"W": p["W"].copy(), "b": p["b"].copy()} for p in self.params])
            if self.early_stopping:
                if monitor < best_loss - 1e-6:
                    best_loss, wait = monitor, 0
                    best_params = [{"W": p["W"].copy(), "b": p["b"].copy()} for p in self.params]
                else:
                    wait += 1
                    if wait >= self.patience:
                        break
        if self.early_stopping and best_params is not None:
            self.params = best_params
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.params:
            raise RuntimeError("模型尚未训练")
        proba, _ = self.forward(X, training=False)
        return proba

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
