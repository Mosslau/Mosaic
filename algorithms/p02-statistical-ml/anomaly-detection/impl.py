"""异常检测 — 手写实现（无监督）

三种互补的"异常分数"（越大越异常）：

- `IsolationForest`：随机切分，异常点更容易被"孤立"（路径短）；
- `LOF`：局部可达密度，异常点比邻居稀疏；
- `KDE`：核密度估计，密度越低越异常（用负 log 密度当分数）。

统一接口：`fit(X)` → `score_samples(X)`（越大越异常）→ `predict(X)`（1 异常 / -1 正常）。
阈值由 `contamination` 在训练分数上取分位数确定。

    model = IsolationForest(contamination=0.05).fit(X_normal)
    scores = model.score_samples(X_test)
    labels = model.predict(X_test)
"""

from __future__ import annotations

import numpy as np


def _c(n: int) -> float:
    """孤立树中 n 个样本的平均路径长度修正项。"""
    if n <= 1:
        return 0.0
    return 2.0 * (np.log(n - 1) + 0.5772156649) - 2.0 * (n - 1) / n


def _sq_dist(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    return (np.sum(A ** 2, 1)[:, None] + np.sum(B ** 2, 1)[None, :]
            - 2.0 * A @ B.T)


class _ITree:
    def __init__(self, rng: np.random.Generator, max_depth: int) -> None:
        self.rng = rng
        self.max_depth = max_depth
        self.root: dict | None = None

    def fit(self, X: np.ndarray) -> _ITree:
        self.root = self._grow(X, depth=0)
        return self

    def _grow(self, X: np.ndarray, depth: int) -> dict:
        n, d = X.shape
        if depth >= self.max_depth or n <= 1:
            return {"n": n}
        lo, hi = X.min(axis=0), X.max(axis=0)
        span = hi - lo
        features = np.flatnonzero(span > 0)
        if len(features) == 0:
            return {"n": n}
        f = int(self.rng.choice(features))
        t = float(self.rng.uniform(lo[f], hi[f]))
        left = X[:, f] <= t
        if left.all() or (~left).all():
            return {"n": n}
        return {"feature": f, "threshold": t,
                "left": self._grow(X[left], depth + 1),
                "right": self._grow(X[~left], depth + 1)}

    def path_length(self, x: np.ndarray) -> float:
        node, depth = self.root, 0
        while "feature" in node:
            node = node["left"] if x[node["feature"]] <= node["threshold"] else node["right"]
            depth += 1
        return depth + _c(node["n"])


class IsolationForest:
    def __init__(self, n_trees: int = 100, sample_size: int = 256,
                 contamination: float = 0.05, random_state: int | None = None) -> None:
        if n_trees < 1:
            raise ValueError("n_trees 至少为 1")
        if not (0 < contamination <= 0.5):
            raise ValueError("contamination 必须在 (0, 0.5]")
        self.n_trees = int(n_trees)
        self.sample_size = int(sample_size)
        self.contamination = float(contamination)
        self.random_state = random_state
        self.trees: list[_ITree] = []
        self._psi = 0
        self.threshold_: float = float("inf")

    def fit(self, X: np.ndarray) -> IsolationForest:
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or len(X) < 2:
            raise ValueError("X 必须是至少 2 行的二维数组")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        rng = np.random.default_rng(self.random_state)
        self._psi = min(self.sample_size, len(X))
        max_depth = int(np.ceil(np.log2(self._psi)))
        self.trees = []
        for _ in range(self.n_trees):
            idx = rng.choice(len(X), self._psi, replace=False)
            self.trees.append(_ITree(rng, max_depth).fit(X[idx]))
        scores = self.score_samples(X)
        self.threshold_ = float(np.quantile(scores, 1 - self.contamination))
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        if not self.trees:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        depth = np.mean([[t.path_length(row) for row in X] for t in self.trees], axis=0)
        return 2.0 ** (-depth / max(_c(self._psi), 1e-12))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.where(self.score_samples(X) > self.threshold_, 1, -1)


class LOF:
    """局部离群因子：LOF 越大越异常。"""

    def __init__(self, n_neighbors: int = 20, contamination: float = 0.05) -> None:
        if n_neighbors < 1:
            raise ValueError("n_neighbors 至少为 1")
        if not (0 < contamination <= 0.5):
            raise ValueError("contamination 必须在 (0, 0.5]")
        self.n_neighbors = int(n_neighbors)
        self.contamination = float(contamination)
        self.threshold_: float = float("inf")
        self._X: np.ndarray | None = None

    def fit(self, X: np.ndarray) -> LOF:
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or len(X) < 3:
            raise ValueError("X 必须是至少 3 行的二维数组")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        self._X = X
        d = np.sqrt(np.maximum(_sq_dist(X, X), 0))
        np.fill_diagonal(d, np.inf)
        k = min(self.n_neighbors, len(X) - 1)
        order = np.argsort(d, axis=1)[:, :k]
        self._k = k
        self._kdist = np.take_along_axis(d, order[:, -1:], axis=1).ravel()
        reach = np.maximum(np.take_along_axis(d, order, axis=1), self._kdist[:, None])
        self._lrd = 1.0 / np.maximum(reach.mean(axis=1), 1e-12)
        self._neighbors = order
        lof = self._lrd[order].mean(axis=1) / np.maximum(self._lrd, 1e-12)
        self.threshold_ = float(np.quantile(lof, 1 - self.contamination))
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        if self._X is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        d = np.sqrt(np.maximum(_sq_dist(X, self._X), 0))
        order = np.argsort(d, axis=1)[:, :self._k]
        reach = np.maximum(np.take_along_axis(d, order, axis=1),
                           self._kdist[order])
        lrd = 1.0 / np.maximum(reach.mean(axis=1), 1e-12)
        return self._lrd[order].mean(axis=1) / np.maximum(lrd, 1e-12)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.where(self.score_samples(X) > self.threshold_, 1, -1)


class KDE:
    """高斯核密度：score = −log density，越大越异常。"""

    def __init__(self, bandwidth: float | None = None, contamination: float = 0.05) -> None:
        if not (0 < contamination <= 0.5):
            raise ValueError("contamination 必须在 (0, 0.5]")
        self.bandwidth = bandwidth
        self.contamination = float(contamination)
        self.threshold_: float = float("inf")
        self._X: np.ndarray | None = None
        self._h: float = 1.0

    def fit(self, X: np.ndarray) -> KDE:
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or len(X) < 2:
            raise ValueError("X 必须是至少 2 行的二维数组")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        self._X = X
        self._h = (float(self.bandwidth) if self.bandwidth is not None
                   else float(len(X) ** (-1.0 / (X.shape[1] + 4)) * X.std(axis=0).mean()))
        scores = self.score_samples(X)
        self.threshold_ = float(np.quantile(scores, 1 - self.contamination))
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        if self._X is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        d2 = np.maximum(_sq_dist(X, self._X), 0) / (self._h ** 2)
        log_kernel = -0.5 * d2
        m = log_kernel.max(axis=1, keepdims=True)
        log_density = (m.ravel() + np.log(np.exp(log_kernel - m).sum(axis=1))
                       - np.log(len(self._X)) - X.shape[1] * np.log(self._h * np.sqrt(2 * np.pi)))
        return -log_density

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.where(self.score_samples(X) > self.threshold_, 1, -1)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
