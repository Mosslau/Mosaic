"""PCA 主成分分析 — demo：同数据双跑 + 三组实验

    uv run python demo.py

    实验一  二维相关数据：方向、方差占比、重建误差
    实验二  手写数字：碎石图、90%/95% 方差需要几个主成分、重建 MSE
    实验三  标准化：协方差 PCA vs 相关矩阵 PCA 的载荷差异
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import PCA
from sklearn.datasets import load_digits

SEED = 0
REPEATS = 3


def make_correlated(n: int = 300, rho: float = 0.9):
    rng = np.random.default_rng(SEED)
    cov = np.array([[1.0, rho], [rho, 1.0]])
    return rng.multivariate_normal([0.0, 0.0], cov, size=n)


def _median_time(fn, repeats: int = REPEATS):
    times = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


def reconstruction_mse(X, k: int) -> float:
    pca = PCA(n_components=k).fit(X)
    Xr = pca.inverse_transform(pca.transform(X))
    return float(np.mean((X - Xr) ** 2))


# ---------------------------------------------------------------- 实验一

def experiment_2d() -> None:
    X = make_correlated()
    print("== 实验一：二维相关数据（rho=0.9） ==")
    hand, t_hand = _median_time(lambda: PCA(n_components=2).fit(X))
    sk, t_sk = _median_time(lambda: framework.fit_pca(X, n_components=2))

    print(f"{'':10} | {'PC1':>14} | {'PC2':>14}")
    print("-" * 44)
    for name, model in (("手写", hand), ("sklearn", sk)):
        print(f"{name:10} | {model.components_[0]} | {model.components_[1]}")
    print(f"\n方差占比：手写 {hand.explained_variance_ratio_}；"
          f"sklearn {sk.explained_variance_ratio_}")
    print(f"k=1 重建 MSE：{reconstruction_mse(X, 1):.4f}；"
          f"k=2：{reconstruction_mse(X, 2):.2e}")

    dot = abs(float(np.dot(hand.components_[0], sk.components_[0])))
    assert dot > 0.999, "第一主成分方向应与 sklearn 一致（允许符号翻转）"
    assert np.allclose(hand.explained_variance_ratio_, sk.explained_variance_ratio_, atol=1e-10)
    print("→ 第一主成分沿 (1,1) 方向，解释了约 95% 的方差；丢掉它重建误差很大。\n")


# ---------------------------------------------------------------- 实验二

def experiment_digits() -> list:
    X, _ = load_digits(return_X_y=True)
    print("== 实验二：手写数字（1797×64）的方差与重建 ==")
    pca = PCA().fit(X)
    _, t_hand = _median_time(lambda: PCA().fit(X))
    _, t_sk = _median_time(lambda: framework.fit_pca(X))
    print(f"全量拟合耗时：手写 {t_hand * 1000:.2f}ms；sklearn {t_sk * 1000:.2f}ms")
    cum = np.cumsum(pca.explained_variance_ratio_)
    k90 = int(np.searchsorted(cum, 0.90) + 1)
    k95 = int(np.searchsorted(cum, 0.95) + 1)
    print(f"前 2 个主成分解释 {cum[1]:.3f}；90% 需 {k90} 个；95% 需 {k95} 个（共 64）")

    print(f"\n{'k':>4} | {'累计方差':>8} | {'重建 MSE':>9}")
    print("-" * 28)
    rows = []
    for k in (1, 2, 5, 10, 20, 30, 50, 64):
        rows.append({"k": k, "cum": float(cum[k - 1]), "mse": reconstruction_mse(X, k)})
        print(f"{k:4d} | {rows[-1]['cum']:8.4f} | {rows[-1]['mse']:9.4f}")

    assert k90 < k95, "90% 方差所需主成分数应少于 95%"
    assert rows[0]["mse"] > rows[2]["mse"] > rows[-1]["mse"]
    assert rows[-1]["mse"] < 1e-12, "保留全部主成分应能无损重建"
    print("\n→ 10 个主成分已保留大部分方差；重建 MSE 随 k 单调降，k=64 时为 0。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_standardize() -> None:
    rng = np.random.default_rng(SEED)
    t = rng.normal(size=500)
    X = np.c_[10.0 * t + rng.normal(scale=0.5, size=500),
              t + rng.normal(scale=0.5, size=500)]
    raw = PCA(n_components=2).fit(X)
    std = PCA(n_components=2, standardize=True).fit(X)
    print("== 实验三：标准化改变「主成分」的含义 ==")
    print(f"原始（协方差）：PC1 = {np.round(raw.components_[0], 4)}，"
          f"占比 {raw.explained_variance_ratio_[0]:.3f}")
    print(f"标准化（相关矩阵）：PC1 = {np.round(std.components_[0], 4)}，"
          f"占比 {std.explained_variance_ratio_[0]:.3f}")

    assert abs(raw.components_[0, 0]) > 0.95, "原始 PCA 会被大尺度特征主导"
    assert min(abs(std.components_[0])) > 0.6, "标准化后两个特征应更均衡"
    print("\n→ 原始 PCA 的 PC1 几乎只由 x0 决定；标准化后 PC1 变成两者的组合。"
          "“主成分”依赖你如何度量距离/方差。\n")


def main() -> None:
    experiment_2d()
    experiment_digits()
    experiment_standardize()


if __name__ == "__main__":
    main()
