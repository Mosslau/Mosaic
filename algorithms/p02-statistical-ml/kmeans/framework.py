"""K-Means 聚类 — 框架对照（无监督估计器）

对照对象：sklearn `KMeans`。
口径：同一份数据、同一 `n_clusters` / `n_init` / `random_state`，比较 inertia、
迭代次数与耗时。sklearn 默认 `init="k-means++"`、`n_init="auto"`，
并用 Elkan 三角不等式 / 并行加速；数学目标一致。
"""

from __future__ import annotations

from sklearn.cluster import KMeans


def fit_kmeans(X, n_clusters: int = 3, random_state: int = 0, n_init: int = 10):
    return KMeans(n_clusters=n_clusters, n_init=n_init, init="k-means++",
                  random_state=random_state).fit(X)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
