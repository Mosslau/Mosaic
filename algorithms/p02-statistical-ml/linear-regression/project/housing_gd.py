"""迁移项目：多特征房价 —— 标准化 + 特征选择 + 正则对照

    uv run python housing_gd.py

与教学示例的差别：
1. 6 个特征、尺度相差 3 个数量级（面积 50–200、房龄 0–50、距离 1–30…）；
2. 混入一个纯噪声特征，用来检验「学到的系数能不能识别无效特征」；
3. 起点不是标准化空间，必须自己处理尺度。

验收标准见 README.md；脚本内逐条断言。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import Model, closed_form, mse  # noqa: E402

FEATURES = ["面积", "房间数", "房龄", "距地铁(km)", "楼层", "噪声特征"]
TRUE_W = np.array([0.8, 12.0, -0.6, -1.5, 0.4, 0.0])


def make_data(n: int = 800, seed: int = 0):
    rng = np.random.default_rng(seed)
    area = rng.uniform(50, 200, n)
    rooms = rng.integers(1, 6, n).astype(float)
    age = rng.uniform(0, 50, n)
    dist = rng.uniform(1, 30, n)
    floor = rng.integers(1, 31, n).astype(float)
    noise = rng.normal(size=n)
    X = np.column_stack([area, rooms, age, dist, floor, noise])
    y = X @ TRUE_W + 40.0 + rng.normal(0, 8, n)
    return X, y


def fit_ridge(X, y, lam: float):
    """带截距的岭回归闭式解（中心化 + 惩罚标准化后的权重）。"""
    n = X.shape[0]
    mu, sigma = X.mean(0), X.std(0)
    sigma = np.where(sigma == 0, 1.0, sigma)
    Xs = (X - mu) / sigma
    w = np.linalg.solve(Xs.T @ Xs + n * lam * np.eye(X.shape[1]), Xs.T @ (y - y.mean()))
    b = float(y.mean() - Xs.mean(0) @ w)
    return w / sigma, float(b - mu @ (w / sigma))


def main() -> None:
    X, y = make_data()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0)

    print("== 数据 ==")
    print(f"样本 {len(y)}，特征 {X.shape[1]}，真实系数 {np.round(TRUE_W, 2).tolist()}")
    print(f"特征标准差：{np.round(X.std(0), 2).tolist()}")

    # ① 不标准化 + lr=0.01：尺度决定步长，必然失控
    with np.errstate(over="ignore", invalid="ignore"):
        raw = Model(lr=0.01, epochs=300, standardize=False).fit(X_tr, y_tr)
    raw_ok = np.isfinite(raw.loss_history[-1])

    # ② 标准化后的手写 GD
    gd = Model(lr=0.05, epochs=30000, tol=1e-12).fit(X_tr, y_tr)
    gd_te = mse(y_te, gd.predict(X_te))

    # ③ 闭式解 / sklearn 线性 / sklearn Ridge（λ=1）
    w_cf, b_cf = closed_form(X_tr, y_tr)
    cf_te = mse(y_te, X_te @ w_cf + b_cf)
    lin = LinearRegression().fit(X_tr, y_tr)
    w_r, b_r = fit_ridge(X_tr, y_tr, lam=0.01)
    ridge_te = mse(y_te, X_te @ w_r + b_r)

    print("\n== 主对照：达到同一精度的代价 ==")
    print(f"{'方法':26} | {'训练 MSE':>9} | {'测试 MSE':>9}")
    print("-" * 54)
    rows = [
        ("手写 GD（不标准化, lr=.01）", raw, raw.predict),
        ("手写 GD（标准化, lr=.05）", gd, gd.predict),
        ("闭式解（手写）", None, lambda Z: Z @ w_cf + b_cf),
        ("sklearn LinearRegression", lin, lin.predict),
        ("Ridge（手写, λ=0.01）", None, lambda Z: Z @ w_r + b_r),
    ]
    for name, model, pred in rows:
        if model is not None:
            tr = mse(y_tr, model.predict(X_tr))
            te = mse(y_te, model.predict(X_te))
        else:
            tr = mse(y_tr, pred(X_tr))
            te = mse(y_te, pred(X_te))
        if not np.isfinite(te):
            print(f"{name:26} | {tr:>9.3e} | {te:>9.3e}")
        else:
            print(f"{name:26} | {tr:9.4f} | {te:9.4f}")

    # ④ 系数识别：噪声特征的权重应当接近 0
    coefs = gd.raw_coef
    print("\n== 学到的系数（标准化 GD，换回原始尺度） ==")
    for name, true, got in zip(FEATURES, TRUE_W, coefs):
        print(f"  {name:10} 真值 {true:7.2f}  学到 {got:7.2f}")
    importance = np.abs(gd.w)          # 标准化空间的系数才可比
    order = np.argsort(-importance)
    print(f"  标准化重要性：{' > '.join(FEATURES[i] for i in order)}")

    # ⑤ 特征选择：去掉噪声特征，测试误差不应变差
    keep = [0, 1, 2, 3, 4]
    w_sel, b_sel = closed_form(X_tr[:, keep], y_tr)
    sel_tr = mse(y_tr, X_tr[:, keep] @ w_sel + b_sel)
    sel_te = mse(y_te, X_te[:, keep] @ w_sel + b_sel)
    print(f"\n去掉噪声特征：训练 {sel_tr:.4f} / 测试 {sel_te:.4f}"
          f"（全特征闭式解测试 {cf_te:.4f}）")

    print("\n== 验收 ==")
    checks = [
        ("标准化 GD 与闭式解测试 MSE 相差 ≤ 1%", abs(gd_te - cf_te) <= 0.01 * cf_te),
        ("不标准化 + lr=0.01 发散（loss 非有限）", not raw_ok),
        ("面积是重要性第一", FEATURES[order[0]] == "面积"),
        ("噪声特征 |标准化权重| < 1.5", abs(gd.w[5]) < 1.5),
        ("去掉噪声特征后测试 MSE 基本不变（≤1%）", sel_te <= cf_te * 1.01),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"

    print(f"\n闭式解 {cf_te:.4f} / 手写 GD {gd_te:.4f} / 去噪声特征 {sel_te:.4f} / "
          f"Ridge {ridge_te:.4f}")
    print("→ 标准化是前提；噪声特征权重接近 0，去掉它测试误差基本不变（差异在噪声范围内）。")


if __name__ == "__main__":
    main()
