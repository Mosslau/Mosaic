"""线性回归 — 真实数据附录：diabetes（442×10）

    uv run python real_data.py

不是新实验，只是在真实回归数据上复核：
闭式解 / 手写 GD / sklearn 的测试 RMSE、R² 是否一致，并看系数符号。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from impl import Model, closed_form  # noqa: E402


def main() -> None:
    X, y = load_diabetes(return_X_y=True)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0)

    w, b = closed_form(X_tr, y_tr)
    gd = Model(lr=0.1, epochs=8000, tol=1e-12).fit(X_tr, y_tr)
    sk = LinearRegression().fit(X_tr, y_tr)

    print(f"样本 {len(y)}（训练 {len(y_tr)} / 测试 {len(y_te)}），特征 {X.shape[1]} 维")
    print(f"{'方法':12} | {'测试 RMSE':>9} | {'测试 R²':>8}")
    print("-" * 36)
    for name, pred in (("闭式解", X_te @ w + b),
                       ("手写 GD", gd.predict(X_te)),
                       ("sklearn", sk.predict(X_te))):
        print(f"{name:12} | {np.sqrt(mean_squared_error(y_te, pred)):9.3f} | "
              f"{r2_score(y_te, pred):8.4f}")
    assert abs(r2_score(y_te, X_te @ w + b) - r2_score(y_te, gd.predict(X_te))) < 1e-6

    names = ["age", "sex", "bmi", "bp", "s1", "s2", "s3", "s4", "s5", "s6"]
    order = np.argsort(-np.abs(w))
    print("\n系数绝对值前 5：" + "、".join(f"{names[j]}({w[j]:+.1f})" for j in order[:5]))
    print("\n→ 真实数据上三种解一致；R²≈0.33，说明线性模型只能解释约三分之一方差。")


if __name__ == "__main__":
    main()
