"""迁移项目：真实数据上的 K-Means —— 手写数字聚类

    uv run python digits.py

数据来自 sklearn 自带的 `load_digits`（1797 个 8×8 手写数字、10 个真实类别）。
与教学示例（二维 3 团）的差别：
1. 真实高维数据（64 维）、10 个簇；
2. 用轮廓系数选 K（不看真实标签），再用 ARI 评估聚类质量；
3. 比较随机初始化与 K-Means++ 的稳定性。
"""

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.metrics import adjusted_rand_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import framework  # noqa: E402
from impl import KMeans, silhouette_score  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    print(f"样本 {len(X)}，特征 {X.shape[1]} 维，真实类别 {len(np.unique(y))} 个")

    t0 = time.perf_counter()
    km = KMeans(n_clusters=10, n_init=10, random_state=0).fit(X)
    dt = time.perf_counter() - t0
    ari = adjusted_rand_score(y, km.labels_)
    sk = framework.fit_kmeans(X, n_clusters=10, random_state=0, n_init=10)
    print(f"\nk=10：inertia {km.inertia_:.1f}（sklearn {sk.inertia_:.1f}），"
          f"ARI {ari:.4f}，迭代 {km.n_iter_}，耗时 {dt:.2f}s")

    print("\nK 扫描（轮廓系数，不看标签）：")
    print(f"{'k':>2} | {'inertia':>10} | {'轮廓系数':>8} | {'ARI':>7}")
    print("-" * 36)
    rows = []
    for k in range(6, 13):
        model = KMeans(n_clusters=k, n_init=5, random_state=0).fit(X)
        sil = silhouette_score(X, model.labels_)
        rows.append({"k": k, "inertia": model.inertia_, "sil": sil,
                     "ari": adjusted_rand_score(y, model.labels_)})
        print(f"{k:2d} | {model.inertia_:10.1f} | {sil:8.4f} | {rows[-1]['ari']:7.4f}")
    chosen = max(rows, key=lambda r: r["sil"])

    print("\n初始化对比（8 个种子，n_init=1）：")
    random_vals, pp_vals = [], []
    for seed in range(8):
        random_vals.append(KMeans(n_clusters=10, n_init=1, init="random",
                                  random_state=seed).fit(X).inertia_)
        pp_vals.append(KMeans(n_clusters=10, n_init=1, init="kmeans++",
                              random_state=seed).fit(X).inertia_)
    print(f"  random   ：均值 {np.mean(random_vals):.0f} ± {np.std(random_vals):.0f}")
    print(f"  kmeans++ ：均值 {np.mean(pp_vals):.0f} ± {np.std(pp_vals):.0f}")

    print("\n== 验收 ==")
    checks = [
        ("k=10 的 ARI ≥ 0.55", ari >= 0.55),
        ("inertia 与 sklearn 差 < 1%", abs(km.inertia_ - sk.inertia_) / sk.inertia_ < 0.01),
        ("轮廓系数选出的 K 在 8–10", 8 <= chosen["k"] <= 10),
        ("K-Means++ 的平均 inertia 更低", np.mean(pp_vals) < np.mean(random_vals)),
        ("簇心数量 = 10", km.cluster_centers_.shape[0] == 10),
        ("轮廓系数已计算（有限数）", np.isfinite(chosen["sil"])),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"

    print(f"\n→ 真实 10 类：k=10 的 ARI {ari:.3f}；轮廓系数选中 k={chosen['k']}"
          f"（ARI {chosen['ari']:.3f}）——无监督选 K 与真实类别数不完全一致。")


if __name__ == "__main__":
    main()
