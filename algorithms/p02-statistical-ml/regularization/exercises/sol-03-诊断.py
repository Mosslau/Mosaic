"""参考解：第 3 题（判断）——三个正则化 bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import Lasso, ridge_closed_form  # noqa: E402


def ridge_missing_n(X, y, lam):
    xm, ym = X.mean(0), y.mean()
    Xc, yc = X - xm, y - ym
    A = Xc.T @ Xc + lam * np.eye(X.shape[1])       # bug：漏了 n
    w = np.linalg.solve(A, Xc.T @ yc)
    return w, float(ym - xm @ w)


def ridge_penalize_intercept(X, y, lam):
    A = np.hstack([X, np.ones((len(X), 1))])
    theta = np.linalg.solve(A.T @ A + len(y) * lam * np.eye(A.shape[1]), A.T @ y)
    return theta[:-1], float(theta[-1])            # bug：截距也被惩罚


def lasso_no_sign(X, y, lam, max_iter=3000, tol=1e-9):
    xm, ym = X.mean(0), y.mean()
    Xc, yc = X - xm, y - ym
    d = (Xc ** 2).sum(0) / len(y)
    w = np.zeros(X.shape[1])
    for _ in range(max_iter):
        delta = 0.0
        for j in range(X.shape[1]):
            r = yc - Xc @ w + Xc[:, j] * w[j]
            rho = float(Xc[:, j] @ r) / len(y)
            new = max(rho - lam, 0.0) / d[j]       # bug：漏了 sign（负系数被抹掉）
            delta = max(delta, abs(new - w[j]))
            w[j] = new
        if delta < tol:
            break
    return w, float(ym - xm @ w)


def main() -> None:
    rng = np.random.default_rng(0)

    X = rng.normal(size=(200, 5))
    y = X @ np.array([3.0, -2.0, 1.5, 0.0, 0.0]) + 1.0 + rng.normal(0, 0.5, 200)
    lam = 1.0
    w_ok, _ = ridge_closed_form(X, y, lam)
    w_bad, _ = ridge_missing_n(X, y, lam)
    print("A 漏乘 n：")
    print(f"   正确 ‖w‖ = {np.linalg.norm(w_ok):.4f}；变体 A ‖w‖ = {np.linalg.norm(w_bad):.4f}")
    assert np.linalg.norm(w_bad) > np.linalg.norm(w_ok) * 1.2

    X2 = rng.normal(10.0, 1.0, size=(200, 2))
    y2 = 10.0 + 2.0 * X2[:, 0] - 1.0 * X2[:, 1] + rng.normal(0, 0.3, 200)
    w_ok2, b_ok = ridge_closed_form(X2, y2, 1.0)
    w_bad2, b_bad = ridge_penalize_intercept(X2, y2, 1.0)
    print("\nB 惩罚截距：")
    print(f"   正确 b = {b_ok:.4f}；变体 B b = {b_bad:.4f}")
    mse_ok = np.mean((X2 @ w_ok2 + b_ok - y2) ** 2)
    mse_bad = np.mean((X2 @ w_bad2 + b_bad - y2) ** 2)
    print(f"   正确 MSE = {mse_ok:.4f}；变体 B MSE = {mse_bad:.4f}")
    assert abs(b_bad) < abs(b_ok) and mse_bad > mse_ok

    X3 = rng.normal(size=(300, 4))
    y3 = X3 @ np.array([2.0, -1.5, 0.0, 0.0]) + rng.normal(0, 0.3, 300)
    w_ok3 = Lasso(lam=0.1).fit(X3, y3).coef
    w_bad3, _ = lasso_no_sign(X3, y3, 0.1)
    print("\nC 软阈值漏符号：")
    print(f"   正确系数 = {np.round(w_ok3, 4).tolist()}")
    print(f"   变体 C   = {np.round(w_bad3, 4).tolist()}")
    assert w_ok3[1] < 0 and w_bad3[1] >= 0, "真实负系数应当被 bug 抹成非负"

    print("\n→ A 正则偏弱；B 截距被压、MSE 变差；C 负系数消失。")


if __name__ == "__main__":
    main()
