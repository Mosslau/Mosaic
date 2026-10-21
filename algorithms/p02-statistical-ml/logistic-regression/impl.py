"""逻辑回归 — 手写实现（监督估计器）

接口与线性回归同族：`fit(X, y)` / `predict(X)`，外加 `predict_proba(X)` 输出概率。
差别只在输出层：sigmoid 把线性组合压到 (0, 1)，用交叉熵而不是 MSE 训练。

    model = Model(lr=0.1, epochs=5000)
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)   # 连续概率
    label = model.predict(X_test)         # 按 threshold 阈值化后的 0/1

本实验要理解的是**交叉熵的梯度为什么仍是 (p − y) 这个干净形式**——推导在 README
「数学推导」段。`class_weight="balanced"` 用来演示类别不平衡下的重加权。
"""

from __future__ import annotations

import numpy as np


def sigmoid(z: np.ndarray) -> np.ndarray:
    """数值稳定版 sigmoid：对 z 的正负分支分别处理，避免 exp 溢出。"""
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def binary_cross_entropy(y_true: np.ndarray, proba: np.ndarray) -> float:
    """BCE = −mean(y·log p + (1−y)·log(1−p))，用 logit 形式避免 log(0)。"""
    y_true = np.asarray(y_true, dtype=float)
    proba = np.asarray(proba, dtype=float)
    if y_true.shape != proba.shape:
        raise ValueError(f"形状不一致：y_true {y_true.shape} vs proba {proba.shape}")
    # 概率截断到 (eps, 1−eps)：p=0/1 是极限情形，直接取 log 会得到 inf
    eps = 1e-15
    p = np.clip(proba, eps, 1.0 - eps)
    return float(-np.mean(y_true * np.log(p) + (1.0 - y_true) * np.log(1.0 - p)))


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[int, int, int, int]:
    """返回 (TP, FP, FN, TN)。"""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    return tp, fp, fn, tn


def precision(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    tp, fp, _, _ = confusion(y_true, y_pred)
    return tp / (tp + fp) if tp + fp else 0.0


def recall(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    tp, _, fn, _ = confusion(y_true, y_pred)
    return tp / (tp + fn) if tp + fn else 0.0


def f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    p, r = precision(y_true, y_pred), recall(y_true, y_pred)
    return 2 * p * r / (p + r) if p + r else 0.0


def roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """ROC AUC 的秩公式（Mann–Whitney U），同分取平均秩。"""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    n_pos = int(y_true.sum())
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    sorted_scores = scores[order]
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j + 2) / 2.0       # 1-based 平均秩
        i = j + 1
    rank_sum_pos = float(ranks[y_true == 1].sum())
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def _as_xy(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
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
    if not np.all((y == 0) | (y == 1)):
        raise ValueError("逻辑回归的 y 必须是 0/1")
    return X, y


class Model:
    """逻辑回归：p = sigmoid(X @ w + b)，交叉熵 + 梯度下降。"""

    def __init__(self, lr: float = 0.1, epochs: int = 5000, tol: float = 1e-10,
                 threshold: float = 0.5, standardize: bool = True,
                 class_weight: str | dict | None = None) -> None:
        if not np.isfinite(lr) or lr <= 0:
            raise ValueError(f"学习率必须为正的有限数，实际 {lr}")
        if epochs < 1:
            raise ValueError(f"epochs 至少为 1，实际 {epochs}")
        if tol < 0:
            raise ValueError(f"tol 不能为负，实际 {tol}")
        if not 0.0 < threshold < 1.0:
            raise ValueError(f"threshold 必须在 (0,1) 内，实际 {threshold}")
        if class_weight not in (None, "balanced") and not isinstance(class_weight, dict):
            raise ValueError("class_weight 只支持 None / 'balanced' / dict")
        if isinstance(class_weight, dict) and not ({0, 1} <= set(class_weight)):
            raise ValueError("class_weight 字典必须同时给出 0 和 1 的权重")
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.tol = float(tol)
        self.threshold = float(threshold)
        self.standardize = bool(standardize)
        self.class_weight = class_weight
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.loss_history: list[float] = []
        self.param_history: list[tuple[np.ndarray, float]] = []
        self.epochs_run: int = 0

    # ------------------------------------------------------------------ 工具

    def _weights(self, y: np.ndarray) -> np.ndarray:
        if self.class_weight is None:
            return np.ones_like(y)
        if self.class_weight == "balanced":
            n = len(y)
            n_pos = max(float(y.sum()), 1.0)
            n_neg = max(float(n - y.sum()), 1.0)
            return np.where(y == 1, n / (2 * n_pos), n / (2 * n_neg))
        if not (0 in self.class_weight and 1 in self.class_weight):
            raise ValueError("class_weight 字典必须同时给出 0 和 1 的权重")
        return np.where(y == 1, float(self.class_weight[1]), float(self.class_weight[0]))

    def _scale(self, X: np.ndarray) -> np.ndarray:
        return (X - self._mu) / self._sigma

    # ------------------------------------------------------------------ 训练

    def fit(self, X: np.ndarray, y: np.ndarray) -> Model:
        """批量梯度下降：p = sigmoid(Xw + b)，grad = Xᵀ(sw·(p − y)) / n。"""
        X, y = _as_xy(X, y)
        self._mu = X.mean(axis=0)
        sigma = X.std(axis=0)
        self._sigma = np.where(sigma == 0.0, 1.0, sigma)
        Xs = self._scale(X)
        sw = self._weights(y)
        n = len(y)

        w = np.zeros(X.shape[1])
        b = 0.0
        self.loss_history = []
        self.param_history = []
        self.epochs_run = 0
        prev = float("inf")

        for _ in range(self.epochs):
            z = Xs @ w + b
            loss = float(np.mean(sw * (np.logaddexp(0.0, z) - y * z)))
            self.loss_history.append(loss)
            self.param_history.append((w.copy(), b))
            self.epochs_run += 1
            if abs(prev - loss) < self.tol:
                break
            err = sigmoid(z) - y
            grad_w = (Xs.T @ (sw * err)) / n
            grad_b = float(np.mean(sw * err))
            w -= self.lr * grad_w
            b -= self.lr * grad_b
            prev = loss

        self.w, self.b = w, b
        return self

    # ------------------------------------------------------------------ 预测

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.w is None:
            raise RuntimeError("模型尚未训练，请先调用 fit(X, y)")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.w.shape[0]:
            raise ValueError(f"X 形状应为 (n, {self.w.shape[0]})，实际 {X.shape}")
        return sigmoid(self._scale(X) @ self.w + self.b)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X) >= self.threshold).astype(int)

    @property
    def raw_coef(self) -> np.ndarray:
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
