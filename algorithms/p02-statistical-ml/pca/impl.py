"""PCA 主成分分析 — 手写实现（无监督估计器）

**无监督，接口没有 y**；但与 K-Means 不同，它不做"分派"，而是做**坐标变换**：
所以形态是 fit(X) → transform(X)，另有 fit_transform(X) 一步到位。

    pca = PCA(n_components=2)
    Z = pca.fit_transform(X)              # 降维后的表示
    X_back = pca.inverse_transform(Z)     # 重建，用于看信息损失
    ratio = pca.explained_variance_ratio_ # 各主成分解释的方差占比

要手写的两个要点（README「数学推导」段写出推导）：
    1. 为什么是协方差矩阵的特征向量？——投影后方差最大等价于 x.T Σ x 最大化，
       在 ||x||=1 约束下用拉格朗日乘子即得 Σx = λx
    2. **中心化是必须的**（否则第一主成分会指向均值方向，只在算协方差不是算二阶矩）
"""

import numpy as np


class PCA:
    """PCA：中心化 → 求协方差矩阵特征分解 → 取前 n_components 个特征向量作投影基。"""

    def __init__(self, n_components: int | None = None, whiten: bool = False) -> None:
        self.n_components = n_components
        self.whiten = whiten
        self.components_: np.ndarray | None = None
        self.mean_: np.ndarray | None = None
        self.explained_variance_: np.ndarray | None = None
        self.explained_variance_ratio_: np.ndarray | None = None

    def fit(self, X: np.ndarray) -> "PCA":
        # TODO: 手写
        #   1. self.mean_ = X.mean(axis=0)；Xc = X - mean_（务必中心化）
        #   2. 协方差矩阵 cov = Xc.T @ Xc / (n - 1)
        #   3. np.linalg.eigh（对称矩阵用它，比 eig 稳）→ 特征值降序排列
        #   4. n_components=None 时保留全部；否则取前 k 个特征向量
        #   5. 记录 explained_variance_（特征值）与 ratio（占比，用于画碎石图）
        raise NotImplementedError("TODO: 手写特征分解求主成分")

    def transform(self, X: np.ndarray) -> np.ndarray:
        # TODO: (X - mean_) @ components_.T；whiten=True 时再除以 sqrt(特征值)
        raise NotImplementedError("TODO: 手写投影变换")

    def inverse_transform(self, Z: np.ndarray) -> np.ndarray:
        # TODO: Z @ components_ + mean_（重建，demo 里用重建误差说明丢掉了几成信息）
        raise NotImplementedError("TODO: 手写逆变换重建")

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        # TODO: fit(X) 后返回 transform(X)
        raise NotImplementedError("TODO: 手写 fit_transform")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/transform，再到 demo.py 跑实验")
