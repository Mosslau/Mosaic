"""参考解：第 3 题（判断）——三个 PCA bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import KFold
from sklearn.neighbors import KNeighborsClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import PCA  # noqa: E402


def pca_no_center(X, k=1):
    """bug A：对 XᵀX 而不是中心化后的协方差做特征分解。"""
    vals, vecs = np.linalg.eigh(X.T @ X / len(X))
    order = np.argsort(vals)[::-1]
    return vecs[:, order][:, :k].T, vals[order]


def pca_no_sort(X, k=1):
    """bug C：eigh 返回升序，直接取前 k 列（没有反转）。"""
    Xc = X - X.mean(0)
    vals, vecs = np.linalg.eigh(Xc.T @ Xc / (len(X) - 1))
    return vecs[:, :k].T, vals[:k]


def main() -> None:
    rng = np.random.default_rng(0)
    base = rng.multivariate_normal([0, 0], [[1, 0.9], [0.9, 1]], size=300)
    X = base + np.array([5.0, 5.0])

    print("A 不中心化：")
    comp_bad, vals_bad = pca_no_center(X)
    comp_ok = PCA(n_components=1).fit(X).components_
    cos = abs(float(np.dot(comp_bad[0], X.mean(0)) / np.linalg.norm(X.mean(0))))
    print(f"   错误 PC1 与均值方向夹角余弦：{cos:.4f}（越接近 1 越糟）")
    print(f"   正确 PC1：{np.round(comp_ok[0], 4)}；错误 PC1：{np.round(comp_bad[0], 4)}")
    assert cos > 0.99

    print("\nB 全量 fit PCA（泄漏）：")
    Xd, yd = load_digits(return_X_y=True)
    Xd, yd = Xd[::2], yd[::2]
    kf = KFold(n_splits=4, shuffle=True, random_state=0)
    correct, leak = [], []
    for tr, va in kf.split(Xd):
        pca = PCA(n_components=20).fit(Xd[tr])
        knn = KNeighborsClassifier(n_neighbors=5).fit(pca.transform(Xd[tr]), yd[tr])
        correct.append(float(np.mean(knn.predict(pca.transform(Xd[va])) == yd[va])))

        pca_all = PCA(n_components=20).fit(Xd)          # 错：测试折也参与 fit
        knn_all = KNeighborsClassifier(n_neighbors=5).fit(
            pca_all.transform(Xd[tr]), yd[tr])
        leak.append(float(np.mean(knn_all.predict(pca_all.transform(Xd[va])) == yd[va])))
    print(f"   正确 CV：{np.mean(correct):.4f}；泄漏 CV：{np.mean(leak):.4f}")
    assert np.mean(leak) >= np.mean(correct)

    print("\nC 不排序特征值：")
    Xd2 = load_digits(return_X_y=True)[0]
    comp_bad2, vals_bad2 = pca_no_sort(Xd2, k=10)
    full = PCA().fit(Xd2)
    print(f"   错误取到的 λ：{np.round(vals_bad2[:3], 4)}（应取最大的）")
    print(f"   正确前三个 λ：{np.round(full.explained_variance_[:3], 4)}")
    assert vals_bad2[0] < full.explained_variance_[0]
    print("\n→ A 方向错；B 泄漏；C 取到最小方差方向。")


if __name__ == "__main__":
    main()
