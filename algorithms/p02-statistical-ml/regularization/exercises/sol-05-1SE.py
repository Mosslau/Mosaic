"""参考解：第 5 题（迁移）——1-SE 规则选 λ

    uv run python sol-05-1SE.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import Ridge, cross_val_mse, mse  # noqa: E402


def make_data(n=300, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 8))
    w = np.array([3.0, -2.0, 1.5, 0.0, 0.0, 0.0, 0.0, 0.0])
    y = X @ w + 1.0 + rng.normal(0.0, 1.5, n)
    return X, y


def main() -> None:
    X, y = make_data()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0)
    lams = np.logspace(-3, 1, 20)
    rows = []
    for lam in lams:
        mean, folds = cross_val_mse(lambda lam=lam: Ridge(lam=lam), X_tr, y_tr, k=5, seed=0)
        se = float(np.std(folds, ddof=1) / np.sqrt(len(folds)))
        test = mse(y_te, Ridge(lam=lam).fit(X_tr, y_tr).predict(X_te))
        rows.append({"lam": float(lam), "mean": mean, "se": se, "test": test})

    best = min(rows, key=lambda r: r["mean"])
    threshold = best["mean"] + best["se"]
    candidates = [r for r in rows if r["mean"] <= threshold]
    one_se = max(candidates, key=lambda r: r["lam"])

    print(f"{'λ':>8} | {'CV 均值':>8} | {'SE':>7} | {'测试 MSE':>9}")
    print("-" * 42)
    for r in rows[::3]:
        mark = " ← 最低" if r is best else (" ← 1-SE" if r is one_se else "")
        print(f"{r['lam']:8.4f} | {r['mean']:8.4f} | {r['se']:7.4f} | {r['test']:9.4f}{mark}")

    print(f"\nCV 最低：λ = {best['lam']:.4f}（均值 {best['mean']:.4f}）；"
          f"1-SE 阈值 = {threshold:.4f}；1-SE 选中 λ = {one_se['lam']:.4f}")
    print(f"测试 MSE：最低点 {best['test']:.4f} vs 1-SE {one_se['test']:.4f}")
    assert one_se["lam"] > best["lam"], "1-SE 规则应选更大的 λ（更简单的模型）"
    assert one_se["test"] <= best["test"] * 1.1, "1-SE 的测试误差不应明显更差"
    print("\n→ 1-SE 用一点偏差换稳定性：模型更简单，测试误差基本不变。")


if __name__ == "__main__":
    main()
