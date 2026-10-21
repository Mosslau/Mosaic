"""参考解：第 5 题（迁移）——重建误差 vs 累计方差选 k

    uv run python sol-05-选k.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import PCA  # noqa: E402


def recon_mse(X, k):
    p = PCA(n_components=k).fit(X)
    return float(np.mean((X - p.inverse_transform(p.transform(X))) ** 2))


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0,
                                              stratify=y)

    mses = {k: recon_mse(X_tr, k) for k in range(1, 41)}
    k_mse = min(k for k, v in mses.items() if v <= 2.0)
    full = PCA().fit(X_tr)
    cum = np.cumsum(full.explained_variance_ratio_)
    k_var = int(np.searchsorted(cum, 0.90) + 1)

    print(f"k_mse（MSE≤2.0）= {k_mse}；k_var（90% 方差）= {k_var}")
    for k in (k_mse, k_var):
        p = PCA(n_components=k).fit(X_tr)
        knn = KNeighborsClassifier(n_neighbors=5).fit(p.transform(X_tr), y_tr)
        acc = float(np.mean(knn.predict(p.transform(X_te)) == y_te))
        print(f"  k={k:2d}：累计方差 {cum[k - 1]:.3f}，重建 MSE {mses[k]:.3f}，"
              f"kNN 测试 {acc:.4f}")
        assert acc >= 0.9
    print("\n→ 重建误差和累计方差都能选 k，但'保留方差'不等于'保留判别信息'。")


if __name__ == "__main__":
    main()
