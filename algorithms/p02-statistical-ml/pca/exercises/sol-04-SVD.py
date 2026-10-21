"""参考解：第 4 题（实现）——SVD 版 PCA

    uv run python sol-04-SVD.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import PCA  # noqa: E402


class SVD_PCA:
    def __init__(self, k=10):
        self.k = k

    def fit(self, X):
        self.mean = X.mean(0)
        Xc = X - self.mean
        _, S, Vt = np.linalg.svd(Xc, full_matrices=False)
        self.components = Vt[:self.k]
        self.variance = S[:self.k] ** 2 / (len(X) - 1)
        return self

    def transform(self, X):
        return (X - self.mean) @ self.components.T

    def inverse_transform(self, Z):
        return Z @ self.components + self.mean


def main() -> None:
    X = load_digits().data[:500]
    a = PCA(n_components=10).fit(X)
    b = SVD_PCA(10).fit(X)
    # 允许每行符号翻转；投影坐标也要按列乘同样的符号
    signs = np.ones(10)
    for i in range(10):
        sign = 1.0 if np.dot(a.components_[i], b.components[i]) >= 0 else -1.0
        signs[i] = sign
        np.testing.assert_allclose(a.components_[i], sign * b.components[i], atol=1e-10)
    np.testing.assert_allclose(a.explained_variance_, b.variance, rtol=1e-10)
    np.testing.assert_allclose(a.transform(X), b.transform(X) * signs, atol=1e-9)
    err = np.mean((X - b.inverse_transform(b.transform(X))) ** 2)
    print(f"SVD 主成分与 eigh 一致；k=10 重建 MSE = {err:.4f}")
    print("→ SVD 不必显式形成协方差，数值上更稳。")


if __name__ == "__main__":
    main()
