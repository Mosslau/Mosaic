"""支持向量机 SVM — 框架对照（监督估计器）

对照对象：sklearn `SVC`（核 SVM）与 `LinearSVC`（线性）。

口径：手写目标与 sklearn 都用 `C·Σ(hinge)`（sum 形式），所以 `C` 直接对应，
不需要乘样本数。`gamma` 两边同口径（RBF）。
"""

from __future__ import annotations

import numpy as np
from sklearn.svm import SVC, LinearSVC


def fit_svc(X: np.ndarray, y: np.ndarray, C: float = 1.0, kernel: str = "rbf",
            gamma: float | None = None) -> SVC:
    return SVC(C=C, kernel=kernel, gamma="scale" if gamma is None else gamma).fit(X, y)


def fit_linear_svc(X: np.ndarray, y: np.ndarray, C: float = 1.0) -> LinearSVC:
    return LinearSVC(C=C, loss="hinge", max_iter=20000, tol=1e-6).fit(X, y)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
