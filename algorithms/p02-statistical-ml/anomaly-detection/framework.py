"""异常检测 — 框架对照（无监督）

对照对象：sklearn `IsolationForest` / `LocalOutlierFactor(novelty=True)` /
`KernelDensity`。口径：同一份训练集、同一 contamination / n_neighbors，
比较 ROC AUC、阈值下的精确率/召回率与耗时。
"""

from __future__ import annotations

from sklearn.ensemble import IsolationForest
from sklearn.neighbors import KernelDensity, LocalOutlierFactor


def fit_iforest(X, contamination: float = 0.05):
    return IsolationForest(n_estimators=100, contamination=contamination,
                           random_state=0).fit(X)


def fit_lof(X, n_neighbors: int = 20, contamination: float = 0.05):
    return LocalOutlierFactor(n_neighbors=n_neighbors, novelty=True,
                              contamination=contamination).fit(X)


def fit_kde(X, bandwidth: float = 0.5):
    return KernelDensity(bandwidth=bandwidth).fit(X)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
