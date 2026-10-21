"""PCA 主成分分析 — 框架对照（无监督估计器）

对照对象：sklearn `PCA`。
sklearn 默认用 **SVD**（对中心化矩阵做奇异值分解），手写版用**协方差矩阵
特征分解**；两者在数学上等价，数值稳定性与复杂度不同。

口径：同一份数据、同一 `n_components`，比较 explained_variance_ratio_、
投影坐标与重建误差。sklearn 还会做符号翻转（svd_flip），手写版用
"绝对值最大分量为正"的约定。
"""

from __future__ import annotations

from sklearn.decomposition import PCA


def fit_pca(X, n_components: int | None = None, whiten: bool = False):
    return PCA(n_components=n_components, whiten=whiten).fit(X)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
