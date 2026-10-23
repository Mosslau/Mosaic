"""Boosting / GBDT — 框架对照（监督估计器）

对照对象：sklearn `GradientBoostingRegressor`（平方损失、回归树）。
口径：同一份数据、同一 `n_estimators` / `learning_rate` / `max_depth` /
`subsample`，比较测试 MSE、R² 与耗时。sklearn 额外做了方差缩减、早停
（`n_iter_no_change`）、缺失值支持与 C 级优化。
"""

from __future__ import annotations

from sklearn.ensemble import (
    AdaBoostClassifier,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
)


def fit_gbr(X, y, n_estimators: int = 100, learning_rate: float = 0.1,
            max_depth: int = 3, subsample: float = 1.0) -> GradientBoostingRegressor:
    return GradientBoostingRegressor(
        n_estimators=n_estimators, learning_rate=learning_rate, max_depth=max_depth,
        subsample=subsample, random_state=0).fit(X, y)


def fit_ada(X, y, n_estimators: int = 50):
    return AdaBoostClassifier(n_estimators=n_estimators, random_state=0).fit(X, y)


def fit_gbc(X, y, n_estimators: int = 50):
    return GradientBoostingClassifier(n_estimators=n_estimators, random_state=0).fit(X, y)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
