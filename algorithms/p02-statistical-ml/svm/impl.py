"""支持向量机 SVM — 手写实现（监督估计器）

两个实现，对应两条求解路线：

- `LinearSVM`：原始问题 + hinge loss，用（子）梯度下降求 `w, b`；
- `KernelSVM`：对偶问题 + SMO（成对坐标上升），支持 linear / rbf / poly 核。

    lin = LinearSVM(C=1.0).fit(X, y)          # y ∈ {-1, +1}
    svm = KernelSVM(C=1.0, kernel="rbf").fit(X, y)

标签约定：内部用 y ∈ {-1, +1}（hinge 的定义域），demo.py 负责与 {0,1} 互转。
"""

from __future__ import annotations

import numpy as np


def hinge_loss(scores: np.ndarray, y: np.ndarray) -> float:
    """平均合页损失：mean(max(0, 1 − y·score))。"""
    scores = np.asarray(scores, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.mean(np.maximum(0.0, 1.0 - y * scores)))


def _check_xy(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if X.ndim != 2:
        raise ValueError(f"X 必须是二维，实际 {X.shape}")
    if y.ndim != 1:
        raise ValueError(f"y 必须是一维，实际 {y.shape}")
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"样本数不一致：{X.shape[0]} vs {y.shape[0]}")
    if X.shape[0] == 0:
        raise ValueError("样本数为 0")
    if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
        raise ValueError("X / y 含 NaN 或 inf")
    if not np.all((y == 1) | (y == -1)):
        raise ValueError("SVM 的 y 必须是 −1 / +1")
    return X, y


def _kernel(A: np.ndarray, B: np.ndarray, kind: str, gamma: float,
            degree: int, coef0: float) -> np.ndarray:
    if kind == "linear":
        return A @ B.T
    if kind == "poly":
        return (gamma * (A @ B.T) + coef0) ** degree
    if kind == "rbf":
        sq = (np.sum(A ** 2, axis=1)[:, None] + np.sum(B ** 2, axis=1)[None, :]
              - 2.0 * A @ B.T)
        return np.exp(-gamma * np.maximum(sq, 0.0))
    raise ValueError(f"未知 kernel：{kind}")


class LinearSVM:
    """原始问题：min ½‖w‖² + C·Σ max(0, 1 − y·(Xw+b))（C 是每个样本的罚金，sum 口径）。"""

    def __init__(self, C: float = 1.0, lr: float = 1e-3, epochs: int = 20000,
                 tol: float = 1e-7, standardize: bool = True) -> None:
        if not np.isfinite(C) or C <= 0:
            raise ValueError(f"C 必须为正的有限数，实际 {C}")
        if not np.isfinite(lr) or lr <= 0:
            raise ValueError(f"lr 必须为正的有限数，实际 {lr}")
        if epochs < 1:
            raise ValueError("epochs 至少为 1")
        if tol < 0:
            raise ValueError("tol 不能为负")
        self.C = float(C)
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.tol = float(tol)
        self.standardize = bool(standardize)
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.loss_history: list[float] = []
        self.param_history: list[tuple[np.ndarray, float]] = []
        self.epochs_run: int = 0

    def _scale(self, X: np.ndarray) -> np.ndarray:
        return (X - self._mu) / self._sigma

    def fit(self, X: np.ndarray, y: np.ndarray) -> LinearSVM:
        X, y = _check_xy(X, y)
        if self.standardize:
            self._mu = X.mean(axis=0)
            sigma = X.std(axis=0)
            self._sigma = np.where(sigma == 0.0, 1.0, sigma)
        else:
            self._mu = np.zeros(X.shape[1])
            self._sigma = np.ones(X.shape[1])
        Xs = self._scale(X)

        w = np.zeros(X.shape[1])
        b = 0.0
        self.loss_history = []
        self.param_history = []
        self.epochs_run = 0
        prev = float("inf")

        for _ in range(self.epochs):
            margins = y * (Xs @ w + b)
            loss = 0.5 * float(w @ w) + self.C * float(np.sum(np.maximum(0, 1 - margins)))
            self.loss_history.append(loss)
            self.param_history.append((w.copy(), b))
            self.epochs_run += 1
            if abs(prev - loss) < self.tol:
                break
            active = margins < 1.0
            if np.any(active):
                grad_w = w - self.C * np.sum(y[active, None] * Xs[active], axis=0)
                grad_b = -self.C * float(np.sum(y[active]))
            else:
                grad_w = w.copy()
                grad_b = 0.0
            w -= self.lr * grad_w
            b -= self.lr * grad_b
            prev = loss

        self.w, self.b = w, b
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.w.shape[0]:
            raise ValueError(f"X 形状应为 (n, {self.w.shape[0]})，实际 {X.shape}")
        return self._scale(X) @ self.w + self.b

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.where(self.decision_function(X) >= 0, 1, -1)

    @property
    def margin(self) -> float:
        """原始特征空间里的几何间隔 2/‖w_raw‖（w_raw = w/σ）。"""
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        return float(2.0 / np.linalg.norm(self.w / self._sigma))

    @property
    def support_(self) -> np.ndarray:
        """原始问题里没有 α；用 margin ≤ 1 近似标出"起作用"的样本。"""
        raise NotImplementedError("LinearSVM 不维护 α；支持向量请用 KernelSVM.support_")


class KernelSVM:
    """对偶问题 + SMO：max Σα − ½ΣΣ α_iα_j y_i y_j K(x_i,x_j)，0≤α_i≤C（sum 口径）。"""

    def __init__(self, C: float = 1.0, kernel: str = "rbf", gamma: float | None = None,
                 degree: int = 3, coef0: float = 1.0, tol: float = 1e-4,
                 max_iter: int = 200, standardize: bool = True) -> None:
        if not np.isfinite(C) or C <= 0:
            raise ValueError(f"C 必须为正的有限数，实际 {C}")
        if kernel not in ("linear", "rbf", "poly"):
            raise ValueError("kernel 只支持 linear / rbf / poly")
        if max_iter < 1:
            raise ValueError("max_iter 至少为 1")
        if tol < 0:
            raise ValueError("tol 不能为负")
        self.C = float(C)
        self.kernel = kernel
        self.gamma = gamma
        self.degree = int(degree)
        self.coef0 = float(coef0)
        self.tol = float(tol)
        self.max_iter = int(max_iter)
        self.standardize = bool(standardize)
        self.alpha: np.ndarray | None = None
        self.b: float = 0.0
        self.X_train: np.ndarray | None = None
        self.y_train: np.ndarray | None = None
        self.n_iter: int = 0

    def _scale(self, X: np.ndarray) -> np.ndarray:
        return (X - self._mu) / self._sigma

    def _kernel_mat(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        return _kernel(A, B, self.kernel, self._gamma, self.degree, self.coef0)

    def fit(self, X: np.ndarray, y: np.ndarray) -> KernelSVM:
        X, y = _check_xy(X, y)
        if self.standardize:
            self._mu = X.mean(axis=0)
            sigma = X.std(axis=0)
            self._sigma = np.where(sigma == 0.0, 1.0, sigma)
        else:
            self._mu = np.zeros(X.shape[1])
            self._sigma = np.ones(X.shape[1])
        Xs = self._scale(X)
        n = len(y)
        self._gamma = (1.0 / (Xs.shape[1] * Xs.var())) if self.gamma is None else float(self.gamma)

        K = self._kernel_mat(Xs, Xs)
        # 与 LinearSVM / sklearn 同口径：原始目标用 C·Σ(hinge)，对偶上界是 C
        upper = self.C
        alpha = np.zeros(n)
        b = 0.0
        f = np.zeros(n)                 # f = K(α⊙y) + b，初始 α=0
        E = f - y                       # E_i = f_i − y_i
        self.n_iter = 0

        for _ in range(self.max_iter):
            changed = 0
            for i in range(n):
                Ei = float(E[i])
                if not ((y[i] * Ei < -self.tol and alpha[i] < upper) or
                        (y[i] * Ei > self.tol and alpha[i] > 0)):
                    continue
                # 按 |Ei−Ej| 从大到小尝试，跳过被边界卡住、无法移动的 j
                order = np.argsort(-np.abs(E - Ei))
                for j in order:
                    if j == i:
                        continue
                    Ej = float(E[j])
                    ai_old, aj_old = alpha[i], alpha[j]
                    if y[i] != y[j]:
                        L = max(0.0, aj_old - ai_old)
                        H = min(upper, upper + aj_old - ai_old)
                    else:
                        L = max(0.0, ai_old + aj_old - upper)
                        H = min(upper, ai_old + aj_old)
                    if H <= L:
                        continue
                    eta = K[i, i] + K[j, j] - 2.0 * K[i, j]
                    if eta <= 0:
                        continue
                    aj = min(H, max(L, aj_old + y[j] * (Ei - Ej) / eta))
                    if abs(aj - aj_old) < 1e-6:
                        continue
                    ai = ai_old + y[i] * y[j] * (aj_old - aj)
                    b_old = b
                    b1 = (b - Ei - y[i] * (ai - ai_old) * K[i, i]
                          - y[j] * (aj - aj_old) * K[i, j])
                    b2 = (b - Ej - y[i] * (ai - ai_old) * K[i, j]
                          - y[j] * (aj - aj_old) * K[j, j])
                    if 0 < ai < upper:
                        b = b1
                    elif 0 < aj < upper:
                        b = b2
                    else:
                        b = (b1 + b2) / 2.0
                    alpha[i], alpha[j] = ai, aj
                    f += ((ai - ai_old) * y[i]) * K[:, i] + ((aj - aj_old) * y[j]) * K[:, j]
                    f += b - b_old
                    E = f - y
                    changed += 1
                    break

            self.n_iter += 1
            if changed == 0:
                break

        self.alpha, self.b = alpha, float(b)
        self.X_train, self.y_train = Xs, y
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if self.alpha is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.X_train.shape[1]:
            raise ValueError(f"X 形状应为 (n, {self.X_train.shape[1]})，实际 {X.shape}")
        Kx = self._kernel_mat(self._scale(X), self.X_train)
        return Kx @ (self.alpha * self.y_train) + self.b

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.where(self.decision_function(X) >= 0, 1, -1)

    @property
    def support_(self) -> np.ndarray:
        if self.alpha is None:
            raise RuntimeError("模型尚未训练")
        return np.flatnonzero(self.alpha > 1e-6)

    @property
    def n_support(self) -> int:
        return int(len(self.support_))

    @property
    def coef_(self) -> np.ndarray:
        """线性核下的原始权重（标准化空间）：w = Σ α_i y_i x_i。"""
        if self.alpha is None:
            raise RuntimeError("模型尚未训练")
        if self.kernel != "linear":
            raise ValueError("coef_ 只对 linear 核有意义")
        return (self.alpha * self.y_train) @ self.X_train

    @property
    def margin(self) -> float:
        if self.kernel != "linear":
            raise ValueError("margin 只在线性核下有几何意义")
        return float(2.0 / np.linalg.norm(self.coef_ / self._sigma))


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
