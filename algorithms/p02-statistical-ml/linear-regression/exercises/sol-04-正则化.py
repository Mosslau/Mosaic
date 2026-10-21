"""参考解：第 4 题（实现）——L2 正则的 GD 版 vs 闭式解

    uv run python sol-04-正则化.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from impl import mse


class RidgeGD:
    """在批量梯度下降上加 L2：grad_w += 2·lam·w（不惩罚 b）。"""

    def __init__(self, lam: float = 1.0, lr: float = 0.05, epochs: int = 200000,
                 tol: float = 0.0) -> None:
        self.lam = lam
        self.lr = lr
        self.epochs = epochs
        self.tol = tol

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RidgeGD":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.mu, sigma = X.mean(0), X.std(0)
        self.sigma = np.where(sigma == 0, 1.0, sigma)
        Xs = (X - self.mu) / self.sigma
        w = np.zeros(X.shape[1])
        b = float(y.mean())
        prev = float("inf")
        for _ in range(self.epochs):
            err = Xs @ w + b - y
            loss = float(np.mean(err ** 2) + self.lam * np.sum(w ** 2))
            if abs(prev - loss) < self.tol:
                break
            grad_w = 2.0 / len(y) * (Xs.T @ err) + 2.0 * self.lam * w
            grad_b = 2.0 / len(y) * err.sum()
            w -= self.lr * grad_w
            b -= self.lr * grad_b
            prev = loss
        self.w, self.b = w, b
        return self

    @property
    def raw_coef(self) -> np.ndarray:
        return self.w / self.sigma

    @property
    def raw_intercept(self) -> float:
        return float(self.b - self.mu @ self.raw_coef)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (np.asarray(X, dtype=float) - self.mu) / self.sigma @ self.w + self.b


def ridge_closed_form(X: np.ndarray, y: np.ndarray, lam: float) -> tuple[np.ndarray, float]:
    """与 RidgeGD 同口径的闭式解：先标准化，再解 (XcᵀXc + nλI)w = Xcᵀyc。

    正则化惩罚的是**标准化空间**的 w（与 GD 版完全一致），最后换回原始尺度。
    """
    n = X.shape[0]
    mu, sigma = X.mean(0), X.std(0)
    sigma = np.where(sigma == 0, 1.0, sigma)
    Xs = (X - mu) / sigma
    ybar = y.mean()
    Xc, yc = Xs - Xs.mean(0), y - ybar
    w_s = np.linalg.solve(Xc.T @ Xc + n * lam * np.eye(X.shape[1]), Xc.T @ yc)
    b_s = float(ybar - Xs.mean(0) @ w_s)
    w_raw = w_s / sigma
    return w_raw, float(b_s - mu @ w_raw)


def main() -> None:
    rng = np.random.default_rng(0)
    n, d = 120, 3
    X = rng.normal(size=(n, d)) @ rng.normal(size=(d, d))   # 制造一些相关性
    true_w = np.array([2.0, -1.0, 0.5])
    y = X @ true_w + 1.0 + rng.normal(0, 0.6, n)
    X_tr, X_te, y_tr, y_te = X[:90], X[90:], y[:90], y[90:]

    print(f"{'lam':>6} | {'GD 的 ‖w‖':>10} | {'闭式解 ‖w‖':>10} | "
          f"{'max|Δw|':>9} | {'训练 MSE':>9} | {'测试 MSE':>9}")
    print("-" * 78)
    norms, train_mses, test_mses = [], [], []
    for lam in (0.0, 0.1, 1.0, 10.0):
        gd = RidgeGD(lam=lam).fit(X_tr, y_tr)
        w_cf, b_cf = ridge_closed_form(X_tr, y_tr, lam)
        diff = float(np.max(np.abs(gd.raw_coef - w_cf)))
        tr = mse(y_tr, gd.predict(X_tr))
        te = mse(y_te, gd.predict(X_te))
        norms.append(float(np.linalg.norm(gd.raw_coef)))
        train_mses.append(tr)
        test_mses.append(te)
        print(f"{lam:6.1f} | {norms[-1]:10.4f} | {np.linalg.norm(w_cf):10.4f} | "
              f"{diff:9.2e} | {tr:9.4f} | {te:9.4f}")
        assert diff < 1e-4, f"lam={lam} 时 GD 与闭式解不一致：{diff}"

    assert all(norms[i] > norms[i + 1] for i in range(len(norms) - 1)), "‖w‖ 应随 λ 增大而下降"
    assert all(train_mses[i] < train_mses[i + 1] for i in range(len(train_mses) - 1)), \
        "训练 MSE 应随 λ 增大而上升"
    print("\n→ ‖w‖ 单调收缩、训练 MSE 单调上升；测试 MSE 先降后升（λ=0.1 附近最好）。")
    assert min(test_mses) < test_mses[0], "正则化应当在这个数据上带来测试误差收益"


if __name__ == "__main__":
    main()
