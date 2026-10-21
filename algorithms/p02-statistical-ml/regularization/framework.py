"""正则化与模型选择 — 框架对照（监督估计器）

sklearn 的 `Ridge` / `Lasso` / `cross_val_score` 与本目录手写版的对应关系：

- `Ridge(alpha=α)` 最小化 ‖y−Xw‖² + α‖w‖²；本目录 Ridge 最小化 (1/n)‖·‖² + λ‖w‖²，
  两边乘 n 得 α = n·λ（**这个换算不做，会误以为实现错了**）。
- `Lasso(alpha=α)` 最小化 (1/(2n))‖y−Xw‖² + α‖w‖₁，与手写版同口径，α = λ。
- `cross_val_score` 默认不做分层/打乱；本实验显式传 `KFold(shuffle=True, random_state)`，
  与手写 KFold 对齐。
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import Lasso as SkLasso
from sklearn.linear_model import Ridge as SkRidge
from sklearn.model_selection import KFold


def fit_ridge(X: np.ndarray, y: np.ndarray, lam: float) -> SkRidge:
    n = len(y)
    return SkRidge(alpha=n * lam, fit_intercept=True).fit(X, y)


def fit_lasso(X: np.ndarray, y: np.ndarray, lam: float) -> SkLasso:
    return SkLasso(alpha=lam, fit_intercept=True, max_iter=50000, tol=1e-10).fit(X, y)


def cv_mse_ridge(X: np.ndarray, y: np.ndarray, lam: float, k: int = 5,
                 seed: int = 0) -> tuple[float, list[float]]:
    """用 sklearn 的 KFold + Ridge 复算手写交叉验证（alpha 按每折样本数换算）。"""
    kf = KFold(n_splits=k, shuffle=True, random_state=seed)
    fold_mses = []
    for train, val in kf.split(X):
        alpha = len(train) * lam
        model = SkRidge(alpha=alpha, fit_intercept=True).fit(X[train], y[train])
        fold_mses.append(float(np.mean((model.predict(X[val]) - y[val]) ** 2)))
    return float(np.mean(fold_mses)), fold_mses


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
