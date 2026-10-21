"""K-Means 聚类 — demo：同数据双跑 + 四组实验

    uv run python demo.py

    实验一  手写 vs sklearn（3 团数据）
    实验二  K 的选择：inertia 肘部 + 轮廓系数
    实验三  初始化敏感性：随机 vs K-Means++
    实验四  局限：各向异性/拉长的簇
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import KMeans, silhouette_score
from sklearn.datasets import make_blobs, make_moons
from sklearn.metrics import adjusted_rand_score

SEED = 0
REPEATS = 3


def make_data(n: int = 300, centers: int = 3, std: float = 0.7):
    return make_blobs(n_samples=n, centers=centers, cluster_std=std,
                      random_state=SEED)


def make_moons_data(n: int = 300):
    return make_moons(n_samples=n, noise=0.05, random_state=SEED)


def _median_time(fn, repeats: int = REPEATS):
    times = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


# ---------------------------------------------------------------- 实验一

def experiment_main() -> None:
    X, y = make_data()
    print("== 实验一：手写 vs sklearn（3 团，k=3，n_init=10） ==")
    print(f"{'方法':14} | {'inertia':>10} | {'ARI':>7} | {'迭代':>4} | {'耗时(ms)':>8}")
    print("-" * 58)
    hand, t_hand = _median_time(lambda: KMeans(n_clusters=3, n_init=10,
                                               random_state=SEED).fit(X))
    sk, t_sk = _median_time(lambda: framework.fit_kmeans(X, n_clusters=3,
                                                         random_state=SEED, n_init=10))

    for name, model, t in (("手写 KMeans", hand, t_hand), ("sklearn", sk, t_sk)):
        labels = model.labels_ if hasattr(model, "labels_") else model.labels_
        print(f"{name:14} | {model.inertia_:10.3f} | "
              f"{adjusted_rand_score(y, labels):7.4f} | {model.n_iter_:4d} | {t * 1000:8.2f}")

    assert abs(hand.inertia_ - sk.inertia_) < 1.0, "inertia 应对齐"
    assert adjusted_rand_score(y, hand.labels_) > 0.9, "三团数据应几乎完全分对"
    print("\n→ 同数据下 inertia/ARI 完全对齐；这个规模上耗时差异主要来自固定开销。\n")


# ---------------------------------------------------------------- 实验二

def experiment_k() -> list:
    X, _ = make_data()
    print("== 实验二：K 的选择（k=1..8） ==")
    print(f"{'k':>2} | {'inertia':>10} | {'轮廓系数':>8}")
    print("-" * 28)
    rows = []
    for k in range(1, 9):
        model = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(X)
        sil = silhouette_score(X, model.labels_) if k > 1 else 0.0
        rows.append({"k": k, "inertia": model.inertia_, "sil": sil})
        print(f"{k:2d} | {model.inertia_:10.3f} | {sil:8.4f}")

    best = max(rows, key=lambda r: r["sil"])
    assert best["k"] == 3, "轮廓系数应选出 k=3"
    print("\n→ inertia 单调降（肘部在 3），轮廓系数峰值也在 k=3。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_init() -> dict:
    X, _ = make_data()
    print("== 实验三：初始化敏感性（20 个种子，n_init=1） ==")
    results = {}
    for init in ("random", "kmeans++"):
        vals = []
        for seed in range(20):
            model = KMeans(n_clusters=3, n_init=1, init=init, random_state=seed).fit(X)
            vals.append(model.inertia_)
        results[init] = vals
        print(f"  {init:9}：中位数 {np.median(vals):8.1f}，最差 {max(vals):8.1f}，"
              f"标准差 {np.std(vals):7.1f}")

    assert np.std(results["kmeans++"]) < np.std(results["random"]), "K-Means++ 应更稳"
    print("\n→ 这组种子上 K-Means++ 的标准差更小；但它不保证每个种子都赢，只是降低期望风险。\n")
    return results


# ---------------------------------------------------------------- 实验四

def experiment_moons() -> None:
    X, y = make_moons_data()
    model = KMeans(n_clusters=2, n_init=10, random_state=SEED).fit(X)
    ari = adjusted_rand_score(y, model.labels_)
    print("== 实验四：局限——非球形簇（双月） ==")
    print(f"  K-Means 的 ARI = {ari:.4f}（理想应接近 1）")
    assert ari < 0.8, "非球形簇上 K-Means 应明显吃亏"
    print("→ K-Means 假设簇是「凸的、各向同性」，双月会被一条直线切开，ARI 掉下来。\n")


def main() -> None:
    experiment_main()
    experiment_k()
    experiment_init()
    experiment_moons()


if __name__ == "__main__":
    main()
