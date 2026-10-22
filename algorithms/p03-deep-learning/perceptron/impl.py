"""感知机 — 手写实现（深度模型 · 判别式）

深度学习的第一块砖：**在线错误驱动更新**，没有损失函数、没有梯度下降。
它跟逻辑回归最本质的差别就在这里——感知机只要求"分对"，不优化概率/间隔。

    p = Perceptron(lr=0.1, epochs=10, random_state=42)
    p.fit(X_train, y_train)        # y ∈ {-1, +1}
    label = p.predict(X_test)

收敛定理只在**线性可分**时成立；不可分时误差会在 epoch 间来回摆。
"""

from __future__ import annotations

import numpy as np


class Perceptron:
    """感知机：y_hat = sign(X @ w + b)，错分即更新。"""

    def __init__(self, lr: float = 0.1, epochs: int = 10,
                 random_state: int | None = None, standardize: bool = True) -> None:
        if not np.isfinite(lr) or lr <= 0:
            raise ValueError(f"学习率必须为正的有限数，实际 {lr}")
        if epochs < 1:
            raise ValueError("epochs 至少为 1")
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.random_state = random_state
        self.standardize = bool(standardize)
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.errors_per_epoch: list[int] = []
        self.param_history: list[tuple[np.ndarray, float]] = []
        self.epochs_run: int = 0
        self._mu: np.ndarray | None = None
        self._sigma: np.ndarray | None = None

    def _scale(self, X: np.ndarray) -> np.ndarray:
        if not self.standardize:
            return X
        return (X - self._mu) / self._sigma

    def fit(self, X: np.ndarray, y: np.ndarray) -> Perceptron:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim != 2 or y.ndim != 1 or len(X) != len(y):
            raise ValueError("X / y 形状不匹配")
        if len(X) == 0:
            raise ValueError("样本数为 0")
        if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
            raise ValueError("X / y 含 NaN 或 inf")
        if not np.all((y == 1) | (y == -1)):
            raise ValueError("感知机的 y 必须是 −1 / +1")

        if self.standardize:
            self._mu = X.mean(axis=0)
            sigma = X.std(axis=0)
            self._sigma = np.where(sigma == 0.0, 1.0, sigma)
        else:
            self._mu = np.zeros(X.shape[1])
            self._sigma = np.ones(X.shape[1])
        Xs = self._scale(X)

        rng = np.random.default_rng(self.random_state)
        self.w = np.zeros(X.shape[1])
        self.b = 0.0
        self.errors_per_epoch = []
        self.param_history = []
        self.epochs_run = 0

        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            errors = 0
            for i in order:
                if y[i] * (Xs[i] @ self.w + self.b) <= 0:
                    self.w += self.lr * y[i] * Xs[i]
                    self.b += self.lr * y[i]
                    errors += 1
            self.errors_per_epoch.append(errors)
            self.param_history.append((self.w.copy(), self.b))
            self.epochs_run += 1
            if errors == 0:
                break
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.w.shape[0]:
            raise ValueError(f"X 形状应为 (n, {self.w.shape[0]})，实际 {X.shape}")
        return self._scale(X) @ self.w + self.b

    def predict(self, X: np.ndarray) -> np.ndarray:
        # 约定 sign(0) = +1：>=0 判正类
        return np.where(self.decision_function(X) >= 0, 1, -1)

    @property
    def raw_coef(self) -> np.ndarray:
        """原始特征空间的 w（标准化逆变换）。"""
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        return self.w / self._sigma

    @property
    def margin(self) -> float:
        """原始空间几何间隔 2/‖w_raw‖；感知机不保证最大化它。"""
        return float(2.0 / np.linalg.norm(self.raw_coef))


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
