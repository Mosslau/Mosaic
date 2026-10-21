"""参考解：第 3 题（判断）——三个 K-Means bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import make_blobs
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import KMeans, _sq_dist  # noqa: E402


def stale_labels(X, k=3, seed=0):
    """bug B：只做一轮"分派→更新中心"，不再用新中心重新分派。"""
    rng = np.random.default_rng(seed)
    centers = X[rng.choice(len(X), k, replace=False)].copy()
    labels = np.argmin(_sq_dist(X, centers), axis=1)
    centers = np.array([X[labels == j].mean(axis=0) for j in range(k)])
    return labels, centers


def main() -> None:
    X, _ = make_blobs(n_samples=300, centers=3, cluster_std=0.7, random_state=0)

    print("A n_init=1 + 随机初始化：")
    ones = [KMeans(n_clusters=3, n_init=1, init="random", random_state=s).fit(X).inertia_
            for s in range(20)]
    tens = [KMeans(n_clusters=3, n_init=10, init="random", random_state=s).fit(X).inertia_
            for s in range(20)]
    print(f"   n_init=1 ：中位数 {np.median(ones):.1f}，最差 {max(ones):.1f}")
    print(f"   n_init=10：中位数 {np.median(tens):.1f}，最差 {max(tens):.1f}")
    assert max(tens) <= max(ones) + 1e-9

    print("\nB 最后不重新分派：")
    labels, centers = stale_labels(X)
    d_own = np.linalg.norm(X - centers[labels], axis=1)
    d_best = np.sqrt(np.min(_sq_dist(X, centers), axis=1))
    bad = int(np.sum(d_own > d_best + 1e-9))
    print(f"   labels 与 centers 错位的样本数：{bad}/{len(X)}")
    assert bad > 0, "旧 labels 应该与最终 centers 错位"

    print("\nC 不标准化：")
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 300)
    Xc = np.c_[rng.normal(0, 1000, 300),     # 大尺度、纯噪声
               y * 10 + rng.normal(0, 1, 300)]  # 小尺度、含真实结构
    raw = KMeans(n_clusters=2, n_init=10, random_state=0).fit(Xc)
    std = KMeans(n_clusters=2, n_init=10, random_state=0).fit(
        StandardScaler().fit_transform(Xc))
    ari_raw = adjusted_rand_score(y, raw.labels_)
    ari_std = adjusted_rand_score(y, std.labels_)
    print(f"   原始 ARI {ari_raw:.3f}；标准化后 ARI {ari_std:.3f}")
    assert ari_raw < ari_std
    print("\n→ A 方差大；B labels 错位；C 大尺度特征淹没了真实结构。")


if __name__ == "__main__":
    main()
