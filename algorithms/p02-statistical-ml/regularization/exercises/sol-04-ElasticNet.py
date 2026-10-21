"""参考解：第 4 题（实现）——ElasticNet（L1 + L2）

    uv run python sol-04-ElasticNet.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import Lasso, Ridge, soft_threshold  # noqa: E402


class ElasticNet:
    """min (1/(2n))‖Xw+b−y‖² + λ₁‖w‖₁ + (λ₂/2)‖w‖²。"""

    def __init__(self, l1: float = 0.1, l2: float = 0.1, max_iter: int = 5000,
                 tol: float = 1e-9) -> None:
        self.l1 = l1
        self.l2 = l2
        self.max_iter = max_iter
        self.tol = tol

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.mu, self.ym = X.mean(0), float(y.mean())
        Xc, yc = X - self.mu, y - self.ym
        d = (Xc ** 2).sum(0) / len(y)
        w = np.zeros(X.shape[1])
        for _ in range(self.max_iter):
            delta = 0.0
            for j in range(X.shape[1]):
                r = yc - Xc @ w + Xc[:, j] * w[j]
                rho = float(Xc[:, j] @ r) / len(y)
                new = soft_threshold(rho, self.l1) / (d[j] + self.l2)
                delta = max(delta, abs(new - w[j]))
                w[j] = new
            if delta < self.tol:
                break
        self.w = w
        self.b = float(self.ym - self.mu @ w)
        return self

    def predict(self, X):
        return np.asarray(X, dtype=float) @ self.w + self.b


def main() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 6))
    y = X @ np.array([3.0, -2.0, 1.5, 0.0, 0.0, 0.0]) + 0.5 + rng.normal(0, 0.5, 200)

    print("极限 1：λ₂=0 应与 Lasso(λ₁) 一致")
    en = ElasticNet(l1=0.1, l2=0.0).fit(X, y)
    la = Lasso(lam=0.1).fit(X, y)
    diff = float(np.max(np.abs(en.w - la.coef)))
    print(f"   最大系数差 = {diff:.2e}")
    assert diff < 1e-6

    print("极限 2：λ₁=0, λ₂=λ 应与 Ridge(λ) 一致")
    en = ElasticNet(l1=0.0, l2=1.0).fit(X, y)
    ri = Ridge(lam=1.0).fit(X, y)
    diff = float(np.max(np.abs(en.w - ri.coef)))
    print(f"   最大系数差 = {diff:.2e}")
    assert diff < 1e-8

    # 相关特征：x2 = x1 + 小噪声
    Xc = rng.normal(size=(300, 3))
    Xc[:, 1] = Xc[:, 0] + 0.05 * rng.normal(size=300)
    yc = 3.0 * Xc[:, 0] + 3.0 * Xc[:, 1] + rng.normal(0, 0.2, 300)
    print("\n相关特征（x2 ≈ x1）：")
    lasso = Lasso(lam=0.2).fit(Xc, yc)
    ridge = Ridge(lam=1.0).fit(Xc, yc)
    enet = ElasticNet(l1=0.1, l2=0.5).fit(Xc, yc)
    nz_l = int(np.sum(np.abs(lasso.coef) > 1e-8))
    print(f"   Lasso      {np.round(lasso.coef, 3).tolist()}（非零 {nz_l} 个）")
    print(f"   Ridge      {np.round(ridge.coef, 3).tolist()}")
    nz_e = int(np.sum(np.abs(enet.w) > 1e-8))
    print(f"   ElasticNet {np.round(enet.w, 3).tolist()}（非零 {nz_e} 个）")
    assert np.sum(np.abs(lasso.coef) > 1e-8) < np.sum(np.abs(enet.w) > 1e-8), \
        "相关特征上 ElasticNet 应比 Lasso 留更多特征"
    print("\n→ 两个极限都对，相关特征上 ElasticNet 更稳。")


if __name__ == "__main__":
    main()
