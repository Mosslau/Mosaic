"""推荐系统 — 手写实现：ItemCF + 矩阵分解 + 流行度基线"""

from __future__ import annotations

import numpy as np


def train_test_mask(R, test_ratio=0.2, seed=0):
    """按已评分位置切分 train/test；返回两个同形状掩码。"""
    rng = np.random.default_rng(seed)
    rated = np.argwhere(R > 0)
    order = rng.permutation(len(rated))
    n_test = int(len(rated) * test_ratio)
    test = np.zeros_like(R, dtype=bool)
    for i in order[:n_test]:
        test[tuple(rated[i])] = True
    train = (R > 0) & ~test
    return train, test


class ItemCF:
    def __init__(self, top_k_neighbors: int = 20) -> None:
        self.top_k_neighbors = top_k_neighbors
        self.sim: np.ndarray | None = None
        self.R: np.ndarray | None = None

    def fit(self, R):
        R = np.asarray(R, dtype=float)
        if R.ndim != 2 or len(R) == 0:
            raise ValueError("R 应为非空 (users, items)")
        self.R = R
        norms = np.linalg.norm(R, axis=0)
        sim = R.T @ R / np.maximum(norms[:, None] * norms[None, :], 1e-12)
        np.fill_diagonal(sim, 0.0)
        self.sim = sim
        return self

    def predict(self, u, i):
        if self.sim is None:
            raise RuntimeError("模型尚未训练")
        rated = self.R[u] > 0
        if not rated.any():
            return 0.0
        s = self.sim[i, rated]
        if self.top_k_neighbors:
            keep = np.argsort(s)[-self.top_k_neighbors:]
            s = s[keep]
            vals = self.R[u, rated][keep]
        else:
            vals = self.R[u, rated]
        denom = np.abs(s).sum()
        return float((s * vals).sum() / denom) if denom > 0 else 0.0

    def recommend(self, u, n=10):
        if self.R is None:
            raise RuntimeError("模型尚未训练")
        scores = np.array([self.predict(u, i) for i in range(self.R.shape[1])])
        scores[self.R[u] > 0] = -np.inf
        return np.argsort(scores)[::-1][:n]


class MatrixFactorization:
    def __init__(self, n_factors=8, lr=0.01, reg=0.05, epochs=30, random_state=0):
        if n_factors < 1 or lr <= 0 or reg < 0 or epochs < 1:
            raise ValueError("参数非法")
        self.n_factors, self.lr, self.reg, self.epochs = n_factors, lr, reg, epochs
        self.random_state = random_state

    def fit(self, R):
        R = np.asarray(R, dtype=float)
        if R.ndim != 2:
            raise ValueError("R 应为二维")
        self.R = R
        rng = np.random.default_rng(self.random_state)
        n_u, n_i = R.shape
        self.P = rng.normal(0, 0.1, (n_u, self.n_factors))
        self.Q = rng.normal(0, 0.1, (n_i, self.n_factors))
        self.bu = np.zeros(n_u)
        self.bi = np.zeros(n_i)
        self.mu = float(R[R > 0].mean()) if (R > 0).any() else 0.0
        self.loss_history = []
        for _ in range(self.epochs):
            for u, i in np.argwhere(R > 0):
                r = R[u, i]
                pred = self.mu + self.bu[u] + self.bi[i] + self.P[u] @ self.Q[i]
                e = r - pred
                self.bu[u] += self.lr * (e - self.reg * self.bu[u])
                self.bi[i] += self.lr * (e - self.reg * self.bi[i])
                pu, qi = self.P[u].copy(), self.Q[i].copy()
                self.P[u] += self.lr * (e * qi - self.reg * pu)
                self.Q[i] += self.lr * (e * pu - self.reg * qi)
            self.loss_history.append(self.rmse(R > 0))
        return self

    def predict(self, u, i):
        if not hasattr(self, "P"):
            raise RuntimeError("模型尚未训练")
        return float(self.mu + self.bu[u] + self.bi[i] + self.P[u] @ self.Q[i])

    def rmse(self, mask, R=None):
        R = self.R if R is None else R
        err = []
        for u, i in np.argwhere(mask):
            err.append((R[u, i] - self.predict(u, i)) ** 2)
        return float(np.sqrt(np.mean(err))) if err else float("nan")

    def recommend(self, u, n=10):
        if not hasattr(self, "P"):
            raise RuntimeError("模型尚未训练")
        scores = self.mu + self.bu[u] + self.bi + self.P[u] @ self.Q.T
        scores[self.R[u] > 0] = -np.inf
        return np.argsort(scores)[::-1][:n]


class Popularity:
    def fit(self, R):
        R = np.asarray(R, dtype=float)
        self.R = R
        self.score = (R > 0).sum(0).astype(float) + R.sum(0) / (R > 0).sum(0).clip(1)
        return self

    def recommend(self, u, n=10):
        s = self.score.copy()
        s[self.R[u] > 0] = -np.inf
        return np.argsort(s)[::-1][:n]


def recall_ndcg(model, R, train, test, k=10, threshold=4.0):
    rec, ndcg = [], []
    for u in range(R.shape[0]):
        rel = set(np.where(test[u] & (R[u] >= threshold))[0])
        if not rel:
            continue
        recs = list(model.recommend(u, k))
        hits = [1 if i in rel else 0 for i in recs]
        rec.append(len(set(recs) & rel) / len(rel))
        dcg = sum(h / np.log2(j + 2) for j, h in enumerate(hits))
        ideal = sum(1 / np.log2(j + 2) for j in range(min(len(rel), k)))
        ndcg.append(dcg / ideal if ideal else 0.0)
    return float(np.mean(rec)), float(np.mean(ndcg))


def make_data(n_users=120, n_items=60, n_factors=5, seed=0):
    rng = np.random.default_rng(seed)
    P = rng.normal(0, 1, (n_users, n_factors))
    Q = rng.normal(0, 1, (n_items, n_factors))
    bu = rng.normal(0, 0.3, n_users)
    bi = rng.normal(0, 0.3, n_items)
    noise = rng.normal(0, 0.3, (n_users, n_items))
    R = np.clip(3 + bu[:, None] + bi[None, :] + P @ Q.T + noise, 1, 5)
    mask = rng.random(R.shape) < 0.2
    R[~mask] = 0
    return R


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
