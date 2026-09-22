#!/usr/bin/env python3
# exercises/sol-01-housing-regression.py —— 练习 1 参考实现：房价预测回归工作流
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（本机已装并实测）
# 运行：python3 sol-01-housing-regression.py（离线可跑，已验证）
# 验证状态：已验证 —— 固定 seed=42，数字可复现；随数据划分/随机种子波动（RMSE ±3~5%）
# 验证块数字实测：baseline(均值) RMSE 29.2 万 / LinearRegression test RMSE 12.0（R² 0.831）→
#                Ridge(α=10) RMSE 11.9；加入 5 个无用随机特征后 LR RMSE 12.0 不变
"""练习 1（房价预测，对应 roadmap）：从零走完整回归流程。

步骤：合成房价数据（面积/房龄/房间数/位置分 → 万元单价）→ train/test 划分 →
先跑均值 baseline（roadmap 必会概念：先建立 baseline 再复杂化）→ 标准化 +
线性回归 / Ridge → RMSE / R² 对比。结论：baseline 只是起点，模型把 RMSE 从
29.2 压到 12.0（≈噪声下界 σ=12）。
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 42
N = 900
FEATS = ["area", "age", "rooms", "location"]


def make_housing(seed: int = SEED) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    area = np.clip(rng.normal(95, 22, N), 25, 200)  # 建筑面积 m²
    age = rng.uniform(0, 15, N)  # 房龄 年
    rooms = rng.integers(2, 5, N).astype(float)  # 卧室数
    loc = rng.uniform(0, 10, N)  # 位置评分 0~10
    X = np.column_stack([area, age, rooms, loc])
    # 真实定价规则：面积 +10 万/20m²? 直接线性 + 噪声
    y = 30 + 1.0 * area - 2.0 * age + 10.0 * rooms + 5.0 * loc + rng.normal(0, 12, N)
    y = np.clip(y, 8, None)  # 单价不可能为负
    idx = rng.permutation(N)
    return X[idx], y[idx]


def main() -> None:
    X, y = make_housing()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED)

    # 1) baseline：永远预测训练均值（回归版「多数类」）
    base_pred = np.full_like(y_te, float(y_tr.mean()))
    base_rmse = mean_squared_error(y_te, base_pred) ** 0.5
    print(f"1) baseline（预测均值 {y_tr.mean():.1f} 万）: test RMSE {base_rmse:.1f} 万")

    # 2) 线性回归（标准化）：特征量纲差异大，线性/距离模型要缩放
    lr = make_pipeline(StandardScaler(), LinearRegression()).fit(X_tr, y_tr)
    tr_rmse = mean_squared_error(y_tr, lr.predict(X_tr)) ** 0.5
    te_rmse = mean_squared_error(y_te, lr.predict(X_te)) ** 0.5
    print(
        f"2) LinearRegression: train RMSE {tr_rmse:.1f} / test RMSE {te_rmse:.1f}"
        f"（test R² {r2_score(y_te, lr.predict(X_te)):.3f}）"
    )

    # 3) Ridge：线性回归加 L2 正则
    for alpha in (1.0, 10.0):
        ridge = make_pipeline(StandardScaler(), Ridge(alpha=alpha)).fit(X_tr, y_tr)
        print(
            f"3) Ridge(α={alpha:g}): test RMSE "
            f"{mean_squared_error(y_te, ridge.predict(X_te)) ** 0.5:.1f}"
        )

    # 4) 无用特征会不会伤模型（数据质量视角：加了 5 个随机噪声列）
    rng = np.random.default_rng(SEED)
    X_noise = np.hstack([X, rng.standard_normal((N, 5))])
    Xn_tr, Xn_te, _, _ = train_test_split(X_noise, y, test_size=0.3, random_state=SEED)
    lr_n = make_pipeline(StandardScaler(), LinearRegression()).fit(Xn_tr, y_tr)
    print(
        f"4) +5 个无用随机特征后: test RMSE "
        f"{mean_squared_error(y_te, lr_n.predict(Xn_te)) ** 0.5:.1f}"
        f"（线性回归能自动忽略无用列）"
    )

    # 验收断言：模型显著优于 baseline
    assert te_rmse < base_rmse * 0.5, "模型应把 RMSE 压到 baseline 的一半以下"
    print(
        "\n验收通过：baseline RMSE {:.1f} → 模型 {:.1f}（{:.0f}% 改善），R² {:.3f}".format(
            base_rmse,
            te_rmse,
            (1 - te_rmse / base_rmse) * 100,
            r2_score(y_te, lr.predict(X_te)),
        )
    )


if __name__ == "__main__":
    main()
