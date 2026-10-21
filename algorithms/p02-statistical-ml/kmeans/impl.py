"""K-Means 聚类 — 手写实现（无监督估计器）

**没有 y**：fit(X) 只吃特征矩阵。目标是最小化簇内平方和（inertia）：

    J = Σ_i ||x_i − μ_{c(i)}||²

两阶段交替：固定簇心 → 最近分派；固定分派 → 簇心取均值。
整体非凸，所以结果依赖初始化：本实现支持 K-Means++ 与随机初始化，
并用 n_init 多次重启取最优。

    km = KMeans(n_clusters=3, n_init=10, random_state=0)
    labels = km.fit_predict(X)
    centers = km.cluster_centers_
"""

from __future__ import annotations

import numpy as np


def kmeans_plus_plus(X: np.ndarray, n_clusters: int,
                     rng: np.random.Generator) -> np.ndarray:
    """K-Means++：第一个簇心均匀随机，之后按 D(x)² 加权采样。"""
    n = len(X)
    if n_clusters > n:
        raise ValueError("n_clusters 不能大于样本数")
    centers = [X[rng.integers(n)]]
    closest = np.sum((X - centers[0]) ** 2, axis=1)
    for _ in range(1, n_clusters):
        total = float(closest.sum())
        if total <= 0:
            idx = int(rng.integers(n))
        else:
            idx = int(rng.choice(n, p=closest / total))
        centers.append(X[idx])
        closest = np.minimum(closest, np.sum((X - X[idx]) ** 2, axis=1))
    return np.array(centers)


def _sq_dist(X: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """(n, k) 的平方欧氏距离，用 ‖x‖²+‖c‖²−2x·c 展开。"""
    return (np.sum(X ** 2, axis=1)[:, None]
            + np.sum(centers ** 2, axis=1)[None, :]
            - 2.0 * X @ centers.T)


def silhouette_score(X: np.ndarray, labels: np.ndarray) -> float:
    """平均轮廓系数：s=(b−a)/max(a,b)，单样本簇记 0。"""
    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels)
    n = len(X)
    if n < 2 or len(np.unique(labels)) < 2:
        return 0.0
    d = np.sqrt(np.maximum(
        np.sum(X ** 2, 1)[:, None] + np.sum(X ** 2, 1)[None, :] - 2 * X @ X.T, 0))
    scores = np.zeros(n)
    for i in range(n):
        same = labels == labels[i]
        same[i] = False
        if not np.any(same):
            scores[i] = 0.0
            continue
        a = float(d[i, same].mean())
        b = float(min(d[i, labels == c].mean()
                      for c in np.unique(labels) if c != labels[i]))
        denom = max(a, b)
        scores[i] = 0.0 if denom == 0 else (b - a) / denom
    return float(scores.mean())


class KMeans:
    """K-Means：n_init 次重启 + K-Means++/随机初始化 + Lloyd 迭代。"""

    def __init__(self, n_clusters: int = 3, max_iter: int = 300, tol: float = 1e-4,
                 n_init: int = 10, random_state: int | None = None,
                 init: str = "kmeans++") -> None:
        if n_clusters < 1:
            raise ValueError("n_clusters 至少为 1")
        if max_iter < 1:
            raise ValueError("max_iter 至少为 1")
        if tol < 0:
            raise ValueError("tol 不能为负")
        if n_init < 1:
            raise ValueError("n_init 至少为 1")
        if init not in ("kmeans++", "random"):
            raise ValueError("init 只支持 kmeans++ / random")
        self.n_clusters = int(n_clusters)
        self.max_iter = int(max_iter)
        self.tol = float(tol)
        self.n_init = int(n_init)
        self.random_state = random_state
        self.init = init
        self.cluster_centers_: np.ndarray | None = None
        self.inertia_: float = float("inf")
        self.labels_: np.ndarray | None = None
        self.n_iter_: int = 0
        self.history_: list[dict] = []

    def _init_centers(self, X: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        if self.init == "kmeans++":
            return kmeans_plus_plus(X, self.n_clusters, rng)
        idx = rng.choice(len(X), self.n_clusters, replace=False)
        return X[idx].copy()

    def _lloyd(self, X: np.ndarray, centers: np.ndarray, record: bool) -> tuple:
        n = len(X)
        history = []
        for it in range(1, self.max_iter + 1):
            d2 = _sq_dist(X, centers)
            labels = np.argmin(d2, axis=1)
            new = centers.copy()
            for j in range(self.n_clusters):
                members = X[labels == j]
                if len(members) == 0:
                    # 空簇：把离自己簇心最远的样本挪过来当新簇心
                    far = int(np.argmax(d2[np.arange(n), labels]))
                    new[j] = X[far]
                else:
                    new[j] = members.mean(axis=0)
            shift = float(np.sum((new - centers) ** 2))
            centers = new
            inertia = float(np.sum(np.min(_sq_dist(X, centers), axis=1)))
            if record:
                history.append({"iter": it, "centers": centers.copy(),
                                "labels": labels.copy(), "inertia": inertia})
            if shift <= self.tol:
                break
        d2 = _sq_dist(X, centers)
        labels = np.argmin(d2, axis=1)
        inertia = float(np.sum(d2[np.arange(n), labels]))
        return centers, labels, inertia, it, history

    def fit(self, X: np.ndarray) -> KMeans:
        X = np.asarray(X, dtype=float)
        if X.ndim != 2:
            raise ValueError(f"X 必须是二维，实际 {X.shape}")
        if len(X) == 0:
            raise ValueError("样本数为 0")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        if self.n_clusters > len(X):
            raise ValueError("n_clusters 不能大于样本数")

        rng = np.random.default_rng(self.random_state)
        best = None
        for run in range(self.n_init):
            init_centers = self._init_centers(X, rng)
            centers, labels, inertia, it, _ = self._lloyd(X, init_centers, record=False)
            if best is None or inertia < best[2] - 1e-12:
                best = (centers, labels, inertia, it)
                # 从这一轮的初始中心重放，记录动画所需的完整路径
                self.history_ = self._lloyd(X, init_centers, record=True)[4]

        self.cluster_centers_, self.labels_, self.inertia_, self.n_iter_ = best
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.cluster_centers_ is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.cluster_centers_.shape[1]:
            raise ValueError("X 特征数与训练集不一致")
        return np.argmin(_sq_dist(X, self.cluster_centers_), axis=1)

    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).labels_

    def transform(self, X: np.ndarray) -> np.ndarray:
        """到各簇心的距离（欧氏）。"""
        if self.cluster_centers_ is None:
            raise RuntimeError("模型尚未训练")
        return np.sqrt(np.maximum(_sq_dist(np.asarray(X, dtype=float),
                                          self.cluster_centers_), 0))


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
