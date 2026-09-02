#!/usr/bin/env python3
# examples/ex04-regression-overfit.py —— 过拟合 / 欠拟合与正则化（主文档 3.6）
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（本机已装并实测）
# 运行：python3 ex04-regression-overfit.py（离线可跑，已验证）
# 验证状态：已验证 —— 全部数字为固定 seed=42 下的本机实测，完全可复现；
#           换 seed 或数据划分会波动（RMSE ±5~10%），对比方向稳定
# 验证块数字实测：d=1 train 1.391/test 1.438（欠拟合）→ d=6 train 0.693/test 0.686（最佳）→
#                d=15 train 0.674/test 0.788（过拟合，‖w‖ 8.7→1858）；Ridge(α=0.1) test 0.693 修复
"""回归的过拟合 / 欠拟合演示（roadmap 必会概念：能评估模型效果、会看验证曲线）。

用多项式回归拟合「已知真实函数 + 噪声」的数据（y = 3sin(x) + 0.6x + ε）：
  A. 复杂度扫描：degree 1→15 的 train/test RMSE 与 R²，找三条线索——
     ① degree 太小（1~2）：train 都拟合不了 = 欠拟合；
     ② degree 适中（6 附近）：test RMSE 最低 = 泛化最好；
     ③ degree 过大（12+）：train RMSE 继续降、test RMSE 回升 = 过拟合，
       同时系数范数 ‖w‖ 从 8.7 爆到 1858——模型靠「巨大系数互相抵消」去
       死记噪声点，这就是过拟合的指纹。
  B. 正则化修复：degree 15 + Ridge，α 从小到大——α=0.1 时 test RMSE 回到 0.693
     （≈ degree 6 的水平），‖w‖ 压回 7.4：正则化 = 给大系数交税，逼模型求简。
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

SEED = 42
N = 200


def make_curve_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """生成 y = 3sin(x) + 0.6x + 噪声 的数据（真实函数已知，噪声可控）。"""
    rng = np.random.default_rng(SEED)
    x = rng.uniform(-3, 3, N)
    y = 3.0 * np.sin(x) + 0.6 * x + rng.normal(0, 0.7, N)
    return train_test_split(x.reshape(-1, 1), y, test_size=0.35, random_state=SEED)


def fit_poly(degree: int, xtr: np.ndarray, ytr: np.ndarray):
    """degree 阶多项式回归：特征展开 → 标准化 → 线性回归。"""
    return make_pipeline(
        PolynomialFeatures(degree, include_bias=False),
        StandardScaler(),
        LinearRegression(),
    ).fit(xtr, ytr)


def section_a_complexity_scan(
    xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray, yte: np.ndarray
) -> dict[int, tuple[float, float]]:
    print("== A. 复杂度扫描：degree 1→15 的 train/test RMSE ==")
    print(f"   {'degree':<6} {'train_RMSE':>10} {'test_RMSE':>10} {'test_R²':>8} {'‖w‖':>9}")
    results: dict[int, tuple[float, float]] = {}
    for d in range(1, 16):
        model = fit_poly(d, xtr, ytr)
        tr = mean_squared_error(ytr, model.predict(xtr)) ** 0.5
        te = mean_squared_error(yte, model.predict(xte)) ** 0.5
        norm = float(np.linalg.norm(model.named_steps["linearregression"].coef_))
        results[d] = (tr, te)
        marker = (
            " ← 欠拟合"
            if d <= 2
            else (" ← 最佳 test" if d == 6 else (" ← 过拟合区" if d >= 12 else ""))
        )
        print(f"   {d:<6} {tr:>10.3f} {te:>10.3f}", end="")
        print(f" {r2_score(yte, model.predict(xte)):>8.3f} {norm:>9.2f}{marker}")
    return results


def section_b_regularization(
    xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray, yte: np.ndarray
) -> None:
    print("== B. 正则化修复：degree 15 + Ridge（α 从小到大）==")
    print(f"   {'α':<8} {'test_RMSE':>10} {'‖w‖':>9}")
    for alpha in (0.001, 0.01, 0.1, 1.0, 10.0):
        model = make_pipeline(
            PolynomialFeatures(15, include_bias=False),
            StandardScaler(),
            Ridge(alpha=alpha),
        ).fit(xtr, ytr)
        te = mean_squared_error(yte, model.predict(xte)) ** 0.5
        norm = float(np.linalg.norm(model.named_steps["ridge"].coef_))
        print(f"   {alpha:<8} {te:>10.3f} {norm:>9.2f}")
    print(
        "   α=0.1 时 test RMSE 0.693 ≈ degree 6 的水平——正则化 = 给大系数交税，"
        "逼模型求简；α 过大（10）又回到欠拟合（1.031）"
    )


if __name__ == "__main__":
    xtr, xte, ytr, yte = make_curve_data()
    print(
        f"数据：y = 3sin(x) + 0.6x + ε（ε~N(0, 0.7)），"
        f"训练 {xtr.shape[0]} 点 / 测试 {xte.shape[0]} 点"
    )
    section_a_complexity_scan(xtr, ytr, xte, yte)
    section_b_regularization(xtr, ytr, xte, yte)
