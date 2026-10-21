"""线性回归与梯度下降 — 手写实现（监督估计器）

为什么本目录是这个形态：监督学习有独立的标签 y，所以接口是 `fit(X, y)` / `predict(X)`。
本实验要理解的是**梯度下降本身**，所以训练循环必须手写；闭式解只作为对照与测试基准，
不参与 `fit`。

    model = Model(lr=0.05, epochs=3000)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

变量对应 README「数学推导」段：w 是权重（`self.w`）、b 是偏置（`self.b`）、lr 是学习率、
grad_w / grad_b 是 MSE 对二者的偏导。默认先标准化特征再下降（`standardize=True`），
这是让 GD 在真实尺度上收敛的关键工程手段，README「手写实现要点」解释了为什么。
"""

from __future__ import annotations

import numpy as np


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """均方误差：MSE = mean((y_pred − y_true)²)。"""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.shape != y_pred.shape:
        raise ValueError(f"形状不一致：y_true {y_true.shape} vs y_pred {y_pred.shape}")
    return float(np.mean((y_pred - y_true) ** 2))


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """决定系数：R² = 1 − SS_res / SS_tot；全常数标签时按 sklearn 口径返回 1.0。"""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    if ss_tot == 0.0:
        return 1.0 if ss_res == 0.0 else 0.0
    return 1.0 - ss_res / ss_tot


def closed_form(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """闭式解（最小二乘）：解 (XᵀX)w + Xᵀ1b = Xᵀy，用 lstsq 保证数值稳定。

    只用于对照与测试——`Model.fit` 不用它，否则就绕过了本实验要理解的梯度下降。
    """
    X, y = _as_2d_xy(X, y)
    A = np.hstack([X, np.ones((X.shape[0], 1))])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef[:-1].copy(), float(coef[-1])


def _as_2d_xy(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if X.ndim != 2:
        raise ValueError(f"X 必须是二维（n_samples, n_features），实际 {X.shape}")
    if y.ndim != 1:
        raise ValueError(f"y 必须是一维（n_samples,），实际 {y.shape}")
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"样本数不一致：X {X.shape[0]} vs y {y.shape[0]}")
    if X.shape[0] == 0:
        raise ValueError("样本数为 0，无法训练")
    if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
        raise ValueError("X / y 含 NaN 或 inf")
    return X, y


class Model:
    """线性回归：y_hat = X @ w + b，用批量梯度下降最小化 MSE。"""

    def __init__(self, lr: float = 0.05, epochs: int = 3000, tol: float = 1e-10,
                 standardize: bool = True) -> None:
        if not np.isfinite(lr) or lr <= 0:
            raise ValueError(f"学习率必须为正的有限数，实际 {lr}")
        if epochs < 1:
            raise ValueError(f"epochs 至少为 1，实际 {epochs}")
        if tol < 0:
            raise ValueError(f"tol 不能为负，实际 {tol}")
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.tol = float(tol)
        self.standardize = bool(standardize)
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.loss_history: list[float] = []
        self.param_history: list[tuple[np.ndarray, float]] = []
        self.epochs_run: int = 0
        self._mu: np.ndarray | None = None
        self._sigma: np.ndarray | None = None

    # ------------------------------------------------------------------ 训练

    def _scale(self, X: np.ndarray) -> np.ndarray:
        if not self.standardize:
            return X
        return (X - self._mu) / self._sigma

    def _gradients(self, X: np.ndarray, y: np.ndarray, w: np.ndarray,
                   b: float) -> tuple[np.ndarray, float]:
        """MSE 对 w / b 的偏导：2/n · Xᵀ(y_hat − y) 与 2/n · Σ(y_hat − y)。"""
        n = X.shape[0]
        err = X @ w + b - y
        return (2.0 / n) * X.T @ err, float((2.0 / n) * err.sum())

    def fit(self, X: np.ndarray, y: np.ndarray) -> Model:
        """批量梯度下降，逐轮记录 MSE；相邻两轮 loss 变化 < tol 时提前停止。"""
        X, y = _as_2d_xy(X, y)

        if self.standardize:
            self._mu = X.mean(axis=0)
            sigma = X.std(axis=0)
            sigma = np.where(sigma == 0.0, 1.0, sigma)   # 常数列：不缩放，交给 b 吸收
            self._sigma = sigma
        else:
            self._mu = np.zeros(X.shape[1])
            self._sigma = np.ones(X.shape[1])

        Xs = self._scale(X)
        w = np.zeros(X.shape[1])
        b = float(y.mean())                  # 从均值起步，比 0 更快到达合理区域
        self.loss_history = []
        self.param_history = []
        self.epochs_run = 0
        prev = float("inf")

        for _ in range(self.epochs):
            err = Xs @ w + b - y
            loss = float(np.mean(err ** 2))
            self.loss_history.append(loss)
            self.param_history.append((w.copy(), b))
            self.epochs_run += 1
            if abs(prev - loss) < self.tol:  # 收敛判据：loss 几乎不再变化
                break
            grad_w, grad_b = self._gradients(Xs, y, w, b)
            w -= self.lr * grad_w
            b -= self.lr * grad_b
            prev = loss

        self.w = w
        self.b = b
        return self

    # ------------------------------------------------------------------ 预测

    def predict(self, X: np.ndarray) -> np.ndarray:
        """返回 X @ w + b（在标准化后的空间里计算）；未 fit 时抛 RuntimeError。"""
        if self.w is None:
            raise RuntimeError("模型尚未训练，请先调用 fit(X, y)")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.w.shape[0]:
            raise ValueError(f"X 形状应为 (n, {self.w.shape[0]})，实际 {X.shape}")
        return self._scale(X) @ self.w + self.b

    # ------------------------------------------------------------------ 观察

    @property
    def raw_coef(self) -> np.ndarray:
        """把标准化空间的权重换回原始特征尺度，便于与闭式解/框架系数直接比较。"""
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        return self.w / self._sigma

    @property
    def raw_intercept(self) -> float:
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        return float(self.b - self._mu @ (self.w / self._sigma))


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
