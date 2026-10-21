"""迁移项目：真实回归上的 GBDT —— 糖尿病进展

    uv run python diabetes.py

数据来自 sklearn 自带的 `load_diabetes`（442 个样本、10 维特征、连续目标）。
与教学示例的差别：
1. 真实数据、连续目标；
2. 用独立验证集早停，测试集只报告一次；
3. 与线性回归、随机森林对照，看 Boosting 的偏差-方差取舍。
"""

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import GradientBoostingRegressor  # noqa: E402


def main() -> None:
    X, y = load_diabetes(return_X_y=True)
    X_tmp, X_te, y_tmp, y_te = train_test_split(X, y, test_size=0.2, random_state=0)
    X_tr, X_val, y_tr, y_val = train_test_split(X_tmp, y_tmp, test_size=0.25,
                                                random_state=0)
    print(f"样本 {len(y)}（train {len(y_tr)} / val {len(y_val)} / test {len(y_te)}），"
          f"特征 {X.shape[1]} 维")

    t0 = time.perf_counter()
    gbdt = GradientBoostingRegressor(n_estimators=500, learning_rate=0.05,
                                     max_depth=3, random_state=0).fit(
        X_tr, y_tr, eval_set=(X_val, y_val), early_stopping_rounds=15)
    t_gbdt = time.perf_counter() - t0

    lin = LinearRegression().fit(X_tr, y_tr)
    rf = RandomForestRegressor(n_estimators=200, random_state=0, n_jobs=1).fit(X_tr, y_tr)

    print(f"\nGBDT 早停：{len(gbdt.trees)} 棵（上限 500），验证最优第 {gbdt.best_iteration_} 轮，"
          f"耗时 {t_gbdt:.2f}s")
    print(f"{'模型':18} | {'测试 RMSE':>9} | {'测试 R²':>8}")
    print("-" * 42)
    for name, model in (("GBDT（早停）", gbdt), ("线性回归", lin), ("随机森林", rf)):
        pred = model.predict(X_te)
        print(f"{name:18} | {np.sqrt(mean_squared_error(y_te, pred)):9.3f} | "
              f"{r2_score(y_te, pred):8.4f}")

    gbdt_r2 = r2_score(y_te, gbdt.predict(X_te))
    lin_r2 = r2_score(y_te, lin.predict(X_te))
    rmse = float(np.sqrt(mean_squared_error(y_te, gbdt.predict(X_te))))

    imp = gbdt.feature_importances_
    top = np.argsort(-imp)[:3]
    print("重要性前 3：" + "、".join(f"x{j}({imp[j]:.3f})" for j in top))

    print("\n== 验收 ==")
    checks = [
        ("GBDT 测试 R² ≥ 0.30", gbdt_r2 >= 0.30),
        ("GBDT 不差于线性回归 0.05", gbdt_r2 >= lin_r2 - 0.05),
        ("测试 RMSE < 60", rmse < 60),
        ("早停树数 < 500", len(gbdt.trees) < 500),
        ("验证最优轮与保留树数一致", gbdt.best_iteration_ == len(gbdt.trees)),
        ("重要性归一化", abs(float(imp.sum()) - 1.0) < 1e-9),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print(f"\n→ 真实回归：GBDT R² {gbdt_r2:.3f}（线性 {lin_r2:.3f}），"
          f"早停在 {len(gbdt.trees)} 棵；验证集刹车省下大量树。")


if __name__ == "__main__":
    main()
