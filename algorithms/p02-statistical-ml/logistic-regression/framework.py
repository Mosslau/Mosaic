"""逻辑回归 — 框架对照（监督估计器）

对照对象：sklearn `LogisticRegression`。要点：

- 它默认带 **L2 正则**（`C=1.0`）；本实验的手写版没有正则，所以把 `C` 设到很大
  （`1e6`）近似"无正则"，才可比。
- 它用 lbfgs/牛顿类求解器（二阶信息），不是批量梯度下降；收敛快、每步贵。
- 它内部不做标准化（由调用者负责），本实验传入已标准化的数据以对齐口径。
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


def fit_logreg(X: np.ndarray, y: np.ndarray, C: float = 1e6) -> LogRegWrapper:
    scaler = StandardScaler().fit(X)
    model = LogisticRegression(
        C=C,                       # 大 C ≈ 弱正则，对齐手写版的"无正则"
        solver="lbfgs",
        max_iter=5000,
        tol=1e-10,
    ).fit(scaler.transform(X), y)
    return LogRegWrapper(model, scaler)


class LogRegWrapper:
    """把 StandardScaler + LogisticRegression 包成与手写版一致的接口。"""

    def __init__(self, model: LogisticRegression, scaler: StandardScaler) -> None:
        self.model = model
        self.scaler = scaler

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(self.scaler.transform(X))[:, 1]

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X) >= 0.5).astype(int)

    @property
    def coef(self) -> np.ndarray:
        return self.model.coef_[0] / self.scaler.scale_

    @property
    def intercept(self) -> float:
        return float(self.model.intercept_[0] - self.scaler.mean_ @ self.coef)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
