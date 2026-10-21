"""参考解：第 4 题（实现）——GBDT 特征子采样

    uv run python sol-04-特征子采样.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import _RegTree  # noqa: E402


class GBDTColsample:
    def __init__(self, n_estimators=100, lr=0.1, max_depth=3, m_features=6, seed=0):
        self.n_estimators = n_estimators
        self.lr = lr
        self.max_depth = max_depth
        self.m_features = m_features
        self.seed = seed

    def fit(self, X, y):
        rng = np.random.default_rng(self.seed)
        self.baseline = float(np.mean(y))
        F = np.full(len(y), self.baseline)
        self.parts = []
        p = X.shape[1]
        for _ in range(self.n_estimators):
            cols = rng.choice(p, size=min(self.m_features, p), replace=False)
            tree = _RegTree(self.max_depth).fit(X[:, cols], y - F)
            F += self.lr * tree.predict(X[:, cols])
            self.parts.append((tree, cols))
        return self

    def predict(self, X):
        out = np.full(len(X), self.baseline)
        for tree, cols in self.parts:
            out += self.lr * tree.predict(X[:, cols])
        return out


def main() -> None:
    X_tr, X_te, y_tr, y_te = D.make_multi()
    full = GBDTColsample(m_features=X_tr.shape[1]).fit(X_tr, y_tr)
    sub = GBDTColsample(m_features=6).fit(X_tr, y_tr)
    mse_full = D.mse(y_te, full.predict(X_te))
    mse_sub = D.mse(y_te, sub.predict(X_te))
    print(f"m=p={X_tr.shape[1]}：测试 MSE {mse_full:.3f}")
    print(f"m=6     ：测试 MSE {mse_sub:.3f}（相对 {mse_sub / mse_full:.2%}）")
    assert mse_sub <= mse_full * 1.15, "特征子采样不应让测试 MSE 崩掉"
    print("\n→ colsample 只让每棵树看 6 列，测试误差仍接近全特征；"
          "随机森林是每次划分重抽，GBDT 是每棵树抽一次。")


if __name__ == "__main__":
    main()
