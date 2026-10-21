"""Boosting / GBDT — demo：同数据双跑 + 四组实验

    uv run python demo.py

    实验一  手写 GBDT vs sklearn（1D 非线性回归）
    实验二  学习率扫描（固定 100 棵树）
    实验三  树数与早停（验证集 + early_stopping_rounds）
    实验四  多特征数据上的重要性
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import GradientBoostingRegressor
from sklearn.datasets import make_regression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 3


def make_1d(n: int = 200, noise: float = 0.15):
    rng = np.random.default_rng(SEED)
    x = rng.uniform(-3.0, 3.0, n)
    y = np.sin(x) + noise * rng.normal(size=n)
    return train_test_split(x[:, None], y, test_size=0.3, random_state=SEED)


def make_multi(n: int = 400, p: int = 10, informative: int = 4):
    X, y = make_regression(n_samples=n, n_features=p, n_informative=informative,
                           noise=10.0, shuffle=False, random_state=SEED)
    return train_test_split(X, y, test_size=0.3, random_state=SEED)


def mse(y, p) -> float:
    return float(mean_squared_error(y, p))


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
    X_tr, X_te, y_tr, y_te = make_1d()
    print("== 实验一：手写 GBDT vs sklearn（1D，100 棵，lr=0.1） ==")
    print(f"{'方法':18} | {'训练 MSE':>9} | {'测试 MSE':>9} | {'测试 R²':>8} | {'耗时(ms)':>8}")
    print("-" * 68)
    hand, t_hand = _median_time(lambda: GradientBoostingRegressor(
        n_estimators=100, learning_rate=0.1, max_depth=3, random_state=SEED).fit(X_tr, y_tr))
    sk, t_sk = _median_time(lambda: framework.fit_gbr(X_tr, y_tr, n_estimators=100))

    for name, model, t in (("手写 GBDT", hand, t_hand), ("sklearn GBR", sk, t_sk)):
        pred = model.predict(X_te)
        print(f"{name:18} | {mse(y_tr, model.predict(X_tr)):9.4f} | {mse(y_te, pred):9.4f} | "
              f"{r2_score(y_te, pred):8.4f} | {t * 1000:8.2f}")

    assert abs(mse(y_te, hand.predict(X_te)) - mse(y_te, sk.predict(X_te))) < 0.03
    print("\n→ 同参数下两者测试 MSE 接近；手写慢在逐树 Python 循环。\n")


# ---------------------------------------------------------------- 实验二

def experiment_lr() -> list:
    X_tr, X_te, y_tr, y_te = make_1d()
    print("== 实验二：学习率扫描（100 棵树，depth=3） ==")
    print(f"{'lr':>6} | {'训练 MSE':>9} | {'测试 MSE':>9} | {'最优轮(验证)':>12}")
    print("-" * 46)
    rows = []
    for lr in (0.01, 0.05, 0.1, 0.3, 1.0):
        model = GradientBoostingRegressor(n_estimators=100, learning_rate=lr,
                                          random_state=SEED).fit(X_tr, y_tr)
        rows.append({"lr": lr, "train": mse(y_tr, model.predict(X_tr)),
                     "test": mse(y_te, model.predict(X_te))})
        print(f"{lr:6.2f} | {rows[-1]['train']:9.4f} | {rows[-1]['test']:9.4f} | {'—':>12}")

    assert rows[0]["train"] > rows[-1]["train"], "固定树数下，lr 越小拟合越不足"
    best = min(rows, key=lambda r: r["test"])
    print(f"\n→ lr 小需要更多树；本数据测试最优在 lr={best['lr']}（{best['test']:.4f}）。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_early_stopping() -> dict:
    X_tr, X_te, y_tr, y_te = make_1d()
    X_sub, X_val, y_sub, y_val = train_test_split(X_tr, y_tr, test_size=0.25,
                                                  random_state=SEED)
    print("== 实验三：树数与早停（300 棵上限，lr=0.05） ==")
    full = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                     random_state=SEED).fit(X_sub, y_sub)
    early = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                      random_state=SEED).fit(
        X_sub, y_sub, eval_set=(X_val, y_val), early_stopping_rounds=10)

    print(f"{'模型':18} | {'实际树数':>6} | {'验证 MSE':>9} | {'测试 MSE':>9}")
    print("-" * 50)
    print(f"{'不早停':18} | {len(full.trees):6d} | {'—':>9} | "
          f"{mse(y_te, full.predict(X_te)):9.4f}")
    print(f"{'早停':18} | {len(early.trees):6d} | "
          f"{min(early.val_score_):9.4f} | {mse(y_te, early.predict(X_te)):9.4f}")

    assert early.best_iteration_ is not None and len(early.trees) < 300, "早停应减少树数"
    assert mse(y_te, early.predict(X_te)) <= mse(y_te, full.predict(X_te)) + 0.05
    print(f"\n→ 验证最优在第 {early.best_iteration_} 轮；再训练只会让验证误差变差。\n")
    return {"early": early, "full": full, "val": (X_val, y_val)}


# ---------------------------------------------------------------- 实验四

def experiment_importance() -> None:
    X_tr, X_te, y_tr, y_te = make_multi()
    model = GradientBoostingRegressor(n_estimators=150, learning_rate=0.1,
                                      random_state=SEED).fit(X_tr, y_tr)
    sk = framework.fit_gbr(X_tr, y_tr, n_estimators=150)
    imp = model.feature_importances_
    order = np.argsort(-imp)
    print("== 实验四：多特征重要性（前 6，4 个真特征） ==")
    print(f"{'rank':>4} | {'特征':>4} | {'手写':>7} | {'sklearn':>7}")
    print("-" * 30)
    for rank, j in enumerate(order[:6], 1):
        print(f"{rank:4d} | x{j:<3} | {imp[j]:7.4f} | {sk.feature_importances_[j]:7.4f}")
    assert np.isclose(imp.sum(), 1.0)
    assert set(order[:4].tolist()) == {0, 1, 2, 3}, "前 4 应正好是真特征"
    print("\n→ GBDT 把重要性集中在真特征；与 sklearn 的排序一致。\n")


def main() -> None:
    experiment_main()
    experiment_lr()
    experiment_early_stopping()
    experiment_importance()


if __name__ == "__main__":
    main()
