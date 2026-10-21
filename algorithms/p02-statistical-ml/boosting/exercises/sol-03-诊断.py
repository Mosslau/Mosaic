"""参考解：第 3 题（判断）——三个 GBDT bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import GradientBoostingRegressor, _RegTree  # noqa: E402


def fit_to_y(X, y, n_estimators=100, lr=0.1):
    """bug B：每轮树拟合 y，而不是残差。"""
    F = np.full(len(y), float(np.mean(y)))
    trees = []
    for _ in range(n_estimators):
        tree = _RegTree(max_depth=3).fit(X, y)     # 错：target 不是 y − F
        F += lr * tree.predict(X)
        trees.append(tree)
    return F


def main() -> None:
    X_tr, X_te, y_tr, y_te = D.make_1d()

    print("A 学习率 = 1.0（不缩放）：")
    slow = GradientBoostingRegressor(n_estimators=100, learning_rate=0.05,
                                     random_state=0).fit(X_tr, y_tr)
    fast = GradientBoostingRegressor(n_estimators=100, learning_rate=1.0,
                                     random_state=0).fit(X_tr, y_tr)
    print(f"   lr=0.05：训练 {D.mse(y_tr, slow.predict(X_tr)):.4f}，"
          f"测试 {D.mse(y_te, slow.predict(X_te)):.4f}")
    print(f"   lr=1.00：训练 {D.mse(y_tr, fast.predict(X_tr)):.4f}，"
          f"测试 {D.mse(y_te, fast.predict(X_te)):.4f}")
    assert D.mse(y_tr, fast.predict(X_tr)) < D.mse(y_tr, slow.predict(X_tr))
    assert D.mse(y_te, fast.predict(X_te)) > D.mse(y_te, slow.predict(X_te))

    print("\nB 拟合 y 而非残差：")
    good = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1,
                                     random_state=0).fit(X_tr, y_tr)
    bad_pred = fit_to_y(X_tr, y_tr)
    print(f"   正确：训练 {D.mse(y_tr, good.predict(X_tr)):.4f}")
    print(f"   错误：训练 {D.mse(y_tr, bad_pred):.4f}（几乎卡住）")
    assert D.mse(y_tr, bad_pred) > D.mse(y_tr, good.predict(X_tr)) * 3

    print("\nC 用测试集早停（泄漏）：")
    X_sub, X_val, y_sub, y_val = train_test_split(X_tr, y_tr, test_size=0.25,
                                                  random_state=0)
    val_stop = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                         random_state=0).fit(
        X_sub, y_sub, eval_set=(X_val, y_val), early_stopping_rounds=10)
    test_stop = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                          random_state=0).fit(
        X_sub, y_sub, eval_set=(X_te, y_te), early_stopping_rounds=10)
    val_mse = D.mse(y_te, val_stop.predict(X_te))
    test_mse = D.mse(y_te, test_stop.predict(X_te))
    print(f"   验证集早停：{len(val_stop.trees)} 棵，测试 {val_mse:.4f}")
    print(f"   测试集早停：{len(test_stop.trees)} 棵，测试 {test_mse:.4f}")
    assert test_mse <= val_mse + 1e-12
    print("\n→ A 过冲；B 卡住；C 的测试误差被'选'得更低，不能作为泛化估计。")


if __name__ == "__main__":
    main()
