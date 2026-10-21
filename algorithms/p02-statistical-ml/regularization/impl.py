"""正则化与模型选择 — 手写实现（监督估计器 · 线性模型）

本目录包含两种正则化线性模型与一个交叉验证工具：

    ridge = Ridge(lam=1.0).fit(X, y)          # L2：闭式解
    lasso = Lasso(lam=0.1).fit(X, y)          # L1：坐标下降
    mean, folds = cross_val_mse(lambda: Ridge(lam=1.0), X, y, k=5)

为什么是监督估计器：有独立的 y，接口是 fit/predict。Ridge 有闭式解，Lasso 没有
（L1 不可导），所以一个走矩阵分解、一个走坐标下降——这正是本实验要对比的两条路。
`lam` 是正则强度（越大惩罚越重）；标准化在内部完成，系数会换回原始尺度。
"""

from __future__ import annotations

import numpy as np


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.shape != y_pred.shape:
        raise ValueError(f"形状不一致：{y_true.shape} vs {y_pred.shape}")
    return float(np.mean((y_pred - y_true) ** 2))


def _check_xy(X: np.ndarray, y: np.ndarray, lam: float) -> tuple[np.ndarray, np.ndarray]:
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
    if not np.isfinite(lam) or lam < 0:
        raise ValueError(f"lam 必须是非负有限数，实际 {lam}")
    return X, y


def ridge_closed_form(X: np.ndarray, y: np.ndarray, lam: float) -> tuple[np.ndarray, float]:
    """Ridge 闭式解：中心化后解 (XcᵀXc + nλI)w = Xcᵀyc，b = ȳ − x̄·w。"""
    X, y = _check_xy(X, y, lam)
    n = X.shape[0]
    xm, ym = X.mean(axis=0), float(y.mean())
    Xc, yc = X - xm, y - ym
    A = Xc.T @ Xc + n * lam * np.eye(X.shape[1])
    w = np.linalg.solve(A, Xc.T @ yc)
    return w, float(ym - xm @ w)


def soft_threshold(rho: float, lam: float) -> float:
    """软阈值：|rho| ≤ λ 时压到 0；否则向 0 收缩 λ。"""
    if rho > lam:
        return rho - lam
    if rho < -lam:
        return rho + lam
    return 0.0


class Ridge:
    """L2 正则线性回归：min (1/n)‖Xw + b − y‖² + λ‖w‖²。"""

    def __init__(self, lam: float = 1.0, standardize: bool = False) -> None:
        if not np.isfinite(lam) or lam < 0:
            raise ValueError(f"lam 必须是非负有限数，实际 {lam}")
        self.lam = float(lam)
        self.standardize = bool(standardize)
        self.w: np.ndarray | None = None
        self.b: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> Ridge:
        X, y = _check_xy(X, y, self.lam)
        if self.standardize:
            self._mu = X.mean(axis=0)
            sigma = X.std(axis=0)
            self._sigma = np.where(sigma == 0.0, 1.0, sigma)
            Xs = (X - self._mu) / self._sigma
            w_s, b_s = self._solve(Xs, y, self.lam)
            self.w = w_s / self._sigma
            self.b = float(b_s - self._mu @ self.w)
        else:
            self._mu = np.zeros(X.shape[1])
            self._sigma = np.ones(X.shape[1])
            self.w, self.b = self._solve(X, y, self.lam)
        return self

    @staticmethod
    def _solve(X: np.ndarray, y: np.ndarray, lam: float) -> tuple[np.ndarray, float]:
        n = X.shape[0]
        xm, ym = X.mean(axis=0), float(y.mean())
        Xc, yc = X - xm, y - ym
        A = Xc.T @ Xc + n * lam * np.eye(X.shape[1])
        w = np.linalg.solve(A, Xc.T @ yc)
        return w, float(ym - xm @ w)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.w.shape[0]:
            raise ValueError(f"X 形状应为 (n, {self.w.shape[0]})，实际 {X.shape}")
        return X @ self.w + self.b

    @property
    def coef(self) -> np.ndarray:
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        return self.w.copy()

    @property
    def intercept(self) -> float:
        return float(self.b)


class Lasso:
    """L1 正则线性回归：min (1/(2n))‖Xw + b − y‖² + λ‖w‖₁（坐标下降）。"""

    def __init__(self, lam: float = 0.1, max_iter: int = 5000, tol: float = 1e-8,
                 standardize: bool = False) -> None:
        if not np.isfinite(lam) or lam < 0:
            raise ValueError(f"lam 必须是非负有限数，实际 {lam}")
        if max_iter < 1:
            raise ValueError("max_iter 至少为 1")
        if tol < 0:
            raise ValueError("tol 不能为负")
        self.lam = float(lam)
        self.max_iter = int(max_iter)
        self.tol = float(tol)
        self.standardize = bool(standardize)
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.n_iter: int = 0

    def fit(self, X: np.ndarray, y: np.ndarray) -> Lasso:
        X, y = _check_xy(X, y, self.lam)
        n, p = X.shape
        # 截距总由中心化吸收：即使不标准化，也要先把 X 中心化
        self._mu = X.mean(axis=0)
        if self.standardize:
            sigma = X.std(axis=0)
            self._sigma = np.where(sigma == 0.0, 1.0, sigma)
        else:
            self._sigma = np.ones(p)
        Xs = (X - self._mu) / self._sigma
        yc = y - y.mean()
        denom = (Xs ** 2).sum(axis=0) / n          # 每列的 ‖x_j‖²/n
        w = np.zeros(p)
        self.n_iter = 0

        for it in range(self.max_iter):
            max_delta = 0.0
            for j in range(p):
                residual = yc - Xs @ w + Xs[:, j] * w[j]
                rho = float(Xs[:, j] @ residual) / n
                new = soft_threshold(rho, self.lam) / denom[j] if denom[j] > 0 else 0.0
                max_delta = max(max_delta, abs(new - w[j]))
                w[j] = new
            self.n_iter = it + 1
            if max_delta < self.tol:
                break

        self.w = w / self._sigma
        self.b = float(y.mean() - self._mu @ self.w)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.w.shape[0]:
            raise ValueError(f"X 形状应为 (n, {self.w.shape[0]})，实际 {X.shape}")
        return X @ self.w + self.b

    @property
    def coef(self) -> np.ndarray:
        if self.w is None:
            raise RuntimeError("模型尚未训练")
        return self.w.copy()

    @property
    def intercept(self) -> float:
        return float(self.b)


# ---------------------------------------------------------------- 交叉验证

def kfold_indices(n: int, k: int = 5, shuffle: bool = True,
                  seed: int = 0) -> list[tuple[np.ndarray, np.ndarray]]:
    """返回 k 个 (train_idx, val_idx)。"""
    if k < 2 or k > n:
        raise ValueError(f"k 必须在 [2, {n}] 内，实际 {k}")
    idx = np.arange(n)
    if shuffle:
        np.random.RandomState(seed).shuffle(idx)   # 与 sklearn KFold 同一套置换
    folds = np.array_split(idx, k)
    out = []
    for i in range(k):
        val = folds[i]
        train = np.concatenate([folds[j] for j in range(k) if j != i])
        out.append((train, val))
    return out


def cross_val_mse(make_model, X: np.ndarray, y: np.ndarray, k: int = 5,
                  seed: int = 0) -> tuple[float, list[float]]:
    """K 折交叉验证：返回 (平均验证 MSE, 每折 MSE)。"""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if X.shape[0] != y.shape[0]:
        raise ValueError("X / y 样本数不一致")
    fold_mses = []
    for train, val in kfold_indices(len(y), k=k, seed=seed):
        model = make_model()
        model.fit(X[train], y[train])
        fold_mses.append(mse(y[val], model.predict(X[val])))
    return float(np.mean(fold_mses)), fold_mses


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
