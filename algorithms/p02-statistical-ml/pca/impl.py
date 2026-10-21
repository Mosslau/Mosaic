"""PCA 主成分分析 — 手写实现（无监督估计器）

**无监督，接口没有 y**；不做"分派"，而是做**坐标变换**：

    pca = PCA(n_components=2)
    Z = pca.fit_transform(X)              # 降维后的表示
    X_back = pca.inverse_transform(Z)     # 重建，用来看信息损失
    ratio = pca.explained_variance_ratio_ # 各主成分解释的方差占比

两个要点：
1. 主成分是协方差矩阵的特征向量：在 ‖v‖=1 下最大化 vᵀΣv，拉格朗日乘子给出 Σv=λv；
2. **中心化是必须的**，否则第一主成分会指向均值方向。
"""

from __future__ import annotations

import numpy as np


class PCA:
    """PCA：中心化 → 协方差特征分解 → 取前 k 个特征向量作投影基。"""

    def __init__(self, n_components: int | float | None = None,
                 standardize: bool = False, whiten: bool = False) -> None:
        if n_components is not None:
            if isinstance(n_components, float):
                if not (0 < n_components < 1):
                    raise ValueError("浮点 n_components 必须在 (0,1) 内（方差占比）")
            elif n_components < 1:
                raise ValueError("n_components 至少为 1")
        self.n_components = n_components
        self.standardize = bool(standardize)
        self.whiten = bool(whiten)
        self.components_: np.ndarray | None = None
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None
        self.explained_variance_: np.ndarray | None = None
        self.explained_variance_ratio_: np.ndarray | None = None
        self.singular_values_: np.ndarray | None = None
        self.n_features_in_: int | None = None

    def fit(self, X: np.ndarray) -> PCA:
        X = np.asarray(X, dtype=float)
        if X.ndim != 2:
            raise ValueError(f"X 必须是二维，实际 {X.shape}")
        if len(X) < 2:
            raise ValueError("至少需要 2 个样本")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")

        self.n_features_in_ = X.shape[1]
        self.mean_ = X.mean(axis=0)
        if self.standardize:
            sigma = X.std(axis=0)
            self.scale_ = np.where(sigma == 0.0, 1.0, sigma)
        else:
            self.scale_ = np.ones(X.shape[1])
        Xc = (X - self.mean_) / self.scale_

        cov = Xc.T @ Xc / (len(X) - 1)
        eigvals, eigvecs = np.linalg.eigh(cov)      # 对称矩阵，升序
        order = np.argsort(eigvals)[::-1]
        eigvals, eigvecs = eigvals[order], eigvecs[:, order]
        eigvals = np.maximum(eigvals, 0.0)          # 数值误差可能产生 −1e-16

        # 符号约定：每个主成分绝对值最大的分量为正，保证可复现
        for j in range(eigvecs.shape[1]):
            idx = int(np.argmax(np.abs(eigvecs[:, j])))
            if eigvecs[idx, j] < 0:
                eigvecs[:, j] = -eigvecs[:, j]

        total = float(eigvals.sum())
        ratio = eigvals / total if total > 0 else np.zeros_like(eigvals)
        if self.n_components is None:
            k = len(eigvals)
        elif isinstance(self.n_components, float):
            k = int(np.searchsorted(np.cumsum(ratio), self.n_components) + 1)
            k = min(k, len(eigvals))
        else:
            k = min(int(self.n_components), len(eigvals))

        self.components_ = eigvecs[:, :k].T.copy()
        self.explained_variance_ = eigvals[:k].copy()
        self.explained_variance_ratio_ = ratio[:k].copy()
        self.singular_values_ = np.sqrt(eigvals[:k] * (len(X) - 1))
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.components_ is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.n_features_in_:
            raise ValueError(f"X 形状应为 (n, {self.n_features_in_})，实际 {X.shape}")
        Z = ((X - self.mean_) / self.scale_) @ self.components_.T
        if self.whiten:
            Z = Z / np.sqrt(np.maximum(self.explained_variance_, 1e-12))
        return Z

    def inverse_transform(self, Z: np.ndarray) -> np.ndarray:
        if self.components_ is None:
            raise RuntimeError("模型尚未训练")
        Z = np.asarray(Z, dtype=float)
        if Z.ndim != 2 or Z.shape[1] != self.components_.shape[0]:
            raise ValueError(f"Z 形状应为 (n, {self.components_.shape[0]})，实际 {Z.shape}")
        if self.whiten:
            Z = Z * np.sqrt(np.maximum(self.explained_variance_, 1e-12))
        return (Z @ self.components_) * self.scale_ + self.mean_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
