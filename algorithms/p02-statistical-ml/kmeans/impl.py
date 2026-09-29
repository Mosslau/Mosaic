"""K-Means 聚类 — 手写实现（无监督估计器）

**无监督，所以接口没有 y**：fit(X) 只吃特征矩阵。这是本目录与同族监督估计器
（线性回归 / 逻辑回归 / SVM…）在接口上的根本差别——聚类没有标签可拟合。

    km = KMeans(n_clusters=3, max_iter=300, n_init=10, random_state=42)
    km.fit(X)                       # 无 y
    labels = km.predict(X)          # 每个样本所属簇
    centers = km.cluster_centers_   # 簇心，用于可视化

要手写的两个要点（README「数学推导」段写出推导）：
    1. 两阶段交替的收敛性：固定簇心分派是凸的，固定分派求均值也是凸的，
       但整体目标函数非凸 → 结果依赖初始化，所以必须 n_init 多次取最优
    2. K-Means++ 初始化：不是随机撒点，而是按 D(x)^2 概率加权采样
"""

import numpy as np


def kmeans_plus_plus(X: np.ndarray, n_clusters: int, rng: np.random.Generator) -> np.ndarray:
    """K-Means++ 初始化：第一个簇心随机，后续每个以 D(x)^2 为概率加权选取。"""
    # TODO: 手写——维护每个样本到"最近已选簇心"的距离平方，按其为权重采样下一个
    raise NotImplementedError("TODO: 手写 K-Means++ 初始化")


class KMeans:
    """K-Means：交替执行"分派 → 更新簇心"，直到簇心位移小于 tol。"""

    def __init__(
        self,
        n_clusters: int = 3,
        max_iter: int = 300,
        tol: float = 1e-4,
        n_init: int = 10,
        random_state: int | None = None,
    ) -> None:
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.tol = tol
        self.n_init = n_init
        self.random_state = random_state
        self.cluster_centers_: np.ndarray | None = None
        self.inertia_: float = float("inf")

    def fit(self, X: np.ndarray) -> "KMeans":
        """跑 n_init 次（各用不同种子），保留 inertia 最小的一组簇心。"""
        # TODO: 手写
        #   1. rng = np.random.default_rng(random_state)，循环 n_init 次
        #   2. 每次：kmeans_plus_plus 初始化 → 迭代 {算距离分派 → 求均值更新} 至收敛
        #   3. 目标函数 inertia = Σ ||x - 所属簇心||^2；记录它，最后保留最小者
        #   4. 空簇要处理（重新指定簇心或丢弃），README 说明你的选择
        raise NotImplementedError("TODO: 手写两阶段交替聚类")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: 按最近簇心分派（注意要用平方距离比较，避免开方）
        raise NotImplementedError("TODO: 手写最近簇分派")

    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: fit(X) 后返回 predict(X)
        raise NotImplementedError("TODO: 手写 fit_predict")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
