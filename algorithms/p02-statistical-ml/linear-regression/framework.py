"""线性回归与梯度下降 — 框架对照（监督估计器）

对照对象是 sklearn 的两个同接口估计器：

- `LinearRegression`：闭式解（SVD/最小二乘），与本目录 `impl.closed_form` 同一条数学路线；
- `SGDRegressor`：另一种「梯度」路线，但优化器、学习率调度、正则化都封装在框架里。

本文件只负责调用与返回统一口径的结果，差异归因写在 README「框架对照」段。
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression, SGDRegressor
from sklearn.preprocessing import StandardScaler


def fit_linear(X: np.ndarray, y: np.ndarray) -> LinearRegression:
    """sklearn 的闭式解版本；默认带截距、不做正则化。"""
    return LinearRegression().fit(X, y)


def fit_sgd(X: np.ndarray, y: np.ndarray, epochs: int = 3000,
            random_state: int = 0) -> SGDWrapper:
    """sklearn 的 SGD 版本：内部做标准化 + 常数学习率，便于与手写 GD 对照。"""
    scaler = StandardScaler().fit(X)
    model = SGDRegressor(
        max_iter=epochs,
        tol=1e-10,
        learning_rate="constant",
        eta0=0.05,
        alpha=0.0,             # 与手写版同为「无正则」口径
        early_stopping=False,  # 关掉 sklearn 的提前停止，避免它先停而没收敛
        random_state=random_state,
        fit_intercept=True,
    ).fit(scaler.transform(X), y)
    return SGDWrapper(model, scaler)


class SGDWrapper:
    """把 StandardScaler + SGDRegressor 包成与手写版一致的 predict 接口。"""

    def __init__(self, model: SGDRegressor, scaler: StandardScaler) -> None:
        self.model = model
        self.scaler = scaler

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(self.scaler.transform(X))

    @property
    def coef(self) -> np.ndarray:
        """换算回原始特征尺度（sklearn 在标准化空间里学到的系数要除以尺度）。"""
        return self.model.coef_ / self.scaler.scale_

    @property
    def intercept(self) -> float:
        return float(self.model.intercept_[0] - self.scaler.mean_ @ self.coef)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
