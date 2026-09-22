#!/usr/bin/env python3
# exercises/sol-03-anomaly-detection.py —— 练习 3 参考实现：传感器异常检测
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2 + scipy 1.16.3（已装并实测）
# 运行：python3 sol-03-anomaly-detection.py（离线可跑，已验证）
# 验证状态：已验证 —— 固定 seed=42，数字可复现；随数据/种子波动
# 验证块数字实测：单维 z>3 阈值法 recall 0.340（漏掉 2/3 联合异常）；马氏距离
#                （协方差感知）recall 1.000 / precision 1.000；IsolationForest
#                contamination 猜 0.05 → recall 0.200，猜 0.10 → recall 0.560
"""练习 3（传感器异常检测，对应 roadmap）：无监督异常检测 + 检出评估。

场景：电流与功率强相关（功率≈28×电流）的传感器。故障样本是「电流正常但功率
偏低 80~130W」——每个维度单独看都在正常范围，只有「电流-功率联合」才异常。
任务：用注入的已知异常评估三种方法：
  1. 单维 z>3 阈值法（不看相关性）→ 漏掉大部分联合异常；
  2. 马氏距离（用正常段训练集估计均值/协方差，再算测试点与分布中心的距离，
     numpy 手写即可）→ 相关感知，几乎全抓；
  3. IsolationForest（生产冷启动常用）→ 依赖 contamination 猜得准不准，且对
     「成簇」的异常不敏感。
结论：异常检测没有标签也能跑，但没有标签就无法调阈值——用注入异常做评测、
用「只喂正常段训练」避免污染统计量，是工程上的标准做法。
"""

from __future__ import annotations

import numpy as np
from scipy.stats import chi2
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score

SEED = 42
N_NORMAL_TR = 950
N_NORMAL_TE = 200
N_ANOM = 50


def gen_normal(n: int, rng: np.random.Generator) -> np.ndarray:
    """正常工况：temp / current / vibration 独立，power 与 current 强相关。"""
    current = rng.normal(10, 1.5, n)
    power = 28 * current + rng.normal(0, 18, n)  # 功率 ≈ 28 × 电流（物理关联）
    return np.column_stack(
        [
            rng.normal(30, 4, n),  # temp
            current,
            rng.normal(0.5, 0.2, n),  # vibration
            power,
        ]
    )


def gen_anomaly(n: int, rng: np.random.Generator) -> np.ndarray:
    """异常：电流正常但功率偏低 80~130W（电流传感器旁路）——单维看不出、联合才异常。"""
    cur = rng.normal(10, 1.5, n)
    return np.column_stack(
        [
            rng.normal(30, 4, n),
            cur,
            rng.normal(0.5, 0.2, n),
            28 * cur - rng.uniform(80, 130, n),
        ]
    )


def mahalanobis_flag(
    X: np.ndarray, mu: np.ndarray, cov_inv: np.ndarray, thresh: float
) -> np.ndarray:
    """马氏距离：sqrt((x-μ)ᵀ Σ⁻¹ (x-μ)) 大于阈值判异常。"""
    d2 = np.array([(x - mu) @ cov_inv @ (x - mu) for x in X])
    return d2 > thresh


def main() -> None:
    rng = np.random.default_rng(SEED)
    normal_tr = gen_normal(N_NORMAL_TR, rng)  # 已知正常的训练段（生产里来自历史好数据）
    normal_te = gen_normal(N_NORMAL_TE, rng)  # 评估用正常样本
    anom = gen_anomaly(N_ANOM, rng)  # 注入的已知异常（只用于评测打分）
    X_te = np.vstack([normal_te, anom])
    y_true = np.array([0] * N_NORMAL_TE + [1] * N_ANOM)  # 1 = 异常

    mu = normal_tr.mean(axis=0)
    sd = normal_tr.std(axis=0)
    cov_inv = np.linalg.inv(np.cov(normal_tr.T))
    thresh = chi2.ppf(0.999, df=4)  # 4 维马氏距离² 的 99.9% 阈值

    def report(name: str, pred: np.ndarray) -> None:
        print(
            f"  {name:<42} recall {recall_score(y_true, pred):.3f}"
            f" / precision {precision_score(y_true, pred):.3f}"
            f"（标记 {pred.sum()} 条）"
        )

    print(
        f"== 传感器异常检测（测试集 {len(X_te)} 条：{N_NORMAL_TE} 正常 + {N_ANOM} 注入异常）=="
    )
    z = np.abs((X_te - mu) / sd).max(axis=1)
    report("① 单维 z>3 阈值法", (z > 3).astype(int))
    report(
        "② 马氏距离（相关感知）",
        mahalanobis_flag(X_te, mu, cov_inv, thresh).astype(int),
    )
    for cont in (0.05, 0.10):
        model = IsolationForest(contamination=cont, random_state=SEED).fit(normal_tr)
        report(
            f"③ IsolationForest（contamination 猜 {cont:.2f}）",
            (model.predict(X_te) == -1).astype(int),
        )

    # 冷启动对照：没有历史正常段时把正常+异常混在一起喂 IF
    mix = np.vstack([normal_tr, anom])
    model = IsolationForest(contamination=0.05, random_state=SEED).fit(mix)
    report(
        "③' IsolationForest（混合训练, cont=0.05）",
        (model.predict(X_te) == -1).astype(int),
    )

    # 验收：马氏距离显著优于单维 z；说明 IF 的 contamination 敏感性
    z_rec = recall_score(y_true, (z > 3).astype(int))
    mah_rec = recall_score(
        y_true, mahalanobis_flag(X_te, mu, cov_inv, thresh).astype(int)
    )
    assert mah_rec >= 0.9 and mah_rec > z_rec + 0.3, "马氏距离应显著优于单维 z 阈值"
    print(
        "\n验收通过：马氏距离 {:.2f} > z 阈值 {:.2f}——相关性盲区是单维统计法的软肋；"
        "IF 的 recall 随 contamination 从 0.20 变到 0.56，说明无标签场景要先注入异常定标".format(
            mah_rec, z_rec
        )
    )


if __name__ == "__main__":
    main()
