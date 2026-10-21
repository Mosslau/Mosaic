"""参考解：第 5 题（迁移）——特征扩展后用线性回归拟合曲线

    uv run python sol-05-多项式.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from impl import Model, mse
from sklearn.model_selection import train_test_split


def poly_features(x: np.ndarray, degree: int) -> np.ndarray:
    """把 1 维输入扩展成 [x, x², …, x^degree]。"""
    x = np.asarray(x, dtype=float)
    return np.column_stack([x ** k for k in range(1, degree + 1)])


def main() -> None:
    rng = np.random.default_rng(0)
    x = rng.uniform(-3, 3, size=(120, 1))
    y = 0.5 * x[:, 0] ** 2 - x[:, 0] + 2.0 + rng.normal(0, 0.5, 120)
    X_tr, X_te, y_tr, y_te = train_test_split(x, y, test_size=0.25, random_state=0)

    print(f"{'次数':>4} | {'参数个数':>6} | {'训练 MSE':>9} | {'测试 MSE':>9}")
    print("-" * 44)
    result = {}
    for degree in (1, 2, 9):
        Xtr = poly_features(X_tr, degree)
        Xte = poly_features(X_te, degree)
        model = Model(lr=0.1, epochs=40000, tol=1e-12).fit(Xtr, y_tr)
        tr = mse(y_tr, model.predict(Xtr))
        te = mse(y_te, model.predict(Xte))
        result[degree] = {"train": tr, "test": te, "epochs": model.epochs_run}
        print(f"{degree:>4} | {degree:>6} | {tr:9.4f} | {te:9.4f}")

    assert result[2]["test"] < result[1]["test"], "二次应优于一次（欠拟合）"
    assert result[9]["train"] < result[2]["train"], "九次的训练误差应更低"
    assert result[9]["test"] > result[2]["test"], "九次的测试误差应更高（过拟合）"
    print("\n→ 二次的测试误差最低；九次把噪声也拟合进去，训练更低但测试更差。")
    print(f"   （九次用了 {result[9]['epochs']} 轮，二次用了 {result[2]['epochs']} 轮）")


if __name__ == "__main__":
    main()
