"""参考解：第 4 题（实现）——L2 正则的逻辑回归

    uv run python sol-04-L2.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import accuracy, sigmoid  # noqa: E402


class LogisticL2:
    """BCE + (lam/2)·‖w‖²；梯度多一项 lam·w。"""

    def __init__(self, lam: float = 0.0, lr: float = 0.1, epochs: int = 8000,
                 tol: float = 1e-12) -> None:
        self.lam = lam
        self.lr = lr
        self.epochs = epochs
        self.tol = tol

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.mu, self.sigma = X.mean(0), X.std(0)
        Xs = (X - self.mu) / self.sigma
        w = np.zeros(X.shape[1])
        b = 0.0
        prev = float("inf")
        for _ in range(self.epochs):
            z = Xs @ w + b
            p = sigmoid(z)
            loss = float(np.mean(np.logaddexp(0.0, z) - y * z) + 0.5 * self.lam * w @ w)
            if abs(prev - loss) < self.tol:
                break
            grad_w = (Xs.T @ (p - y)) / len(y) + self.lam * w
            grad_b = float(np.mean(p - y))
            w -= self.lr * grad_w
            b -= self.lr * grad_b
            prev = loss
        self.w, self.b = w, b
        return self

    @property
    def raw_coef(self):
        return self.w / self.sigma

    def predict_proba(self, X):
        return sigmoid((np.asarray(X, dtype=float) - self.mu) / self.sigma @ self.w + self.b)

    def predict(self, X):
        return (self.predict_proba(X) >= 0.5).astype(int)


def main() -> None:
    rng = np.random.default_rng(0)
    n = 400
    X = rng.normal(size=(n, 3))
    y = (rng.random(n) < sigmoid(4.0 * X[:, 0] - 3.0 * X[:, 1] + 2.0 * X[:, 2])).astype(float)
    X_tr, X_te, y_tr, y_te = X[:300], X[300:], y[:300], y[300:]

    print(f"{'lam':>6} | {'‖w‖':>9} | {'训练 BCE':>9} | {'测试 accuracy':>13}")
    print("-" * 48)
    norms, bces, accs = [], [], []
    for lam in (0.0, 0.01, 0.1, 1.0, 10.0):
        model = LogisticL2(lam=lam).fit(X_tr, y_tr)
        norm = float(np.linalg.norm(model.raw_coef))
        bce = float(-np.mean(y_tr * np.log(model.predict_proba(X_tr))
                             + (1 - y_tr) * np.log(1 - model.predict_proba(X_tr))))
        acc = accuracy(y_te, model.predict(X_te))
        norms.append(norm)
        bces.append(bce)
        accs.append(acc)
        print(f"{lam:6.2f} | {norm:9.4f} | {bce:9.4f} | {acc:13.4f}")

    assert all(norms[i] > norms[i + 1] for i in range(len(norms) - 1)), "‖w‖ 应随 λ 增大而下降"
    assert all(bces[i] < bces[i + 1] for i in range(len(bces) - 1)), "训练 BCE 应随 λ 增大而上升"
    assert accs[3] >= 0.9, "适度正则（λ≤1）不应把准确率压垮"
    assert accs[4] < accs[0], "λ=10 过大，应当欠拟合并掉准确率"
    print("\n→ ‖w‖ 被压小、BCE 变大；λ 适中时准确率不变，λ 过大则欠拟合。")


if __name__ == "__main__":
    main()
