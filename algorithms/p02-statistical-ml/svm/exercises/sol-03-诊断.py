"""参考解：第 3 题（判断）——三个 SVM bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import LinearSVM, _kernel  # noqa: E402


def gd_svm(X, y, C, lr=1e-3, epochs=8000, ignore_C=False):
    """最小闭环：ignore_C=True 时梯度漏乘 C。"""
    w = np.zeros(X.shape[1])
    b = 0.0
    for _ in range(epochs):
        m = y * (X @ w + b)
        act = m < 1
        if np.any(act):
            factor = 1.0 if ignore_C else C
            gw = w - factor * np.sum(y[act, None] * X[act], axis=0)
            gb = -factor * float(np.sum(y[act]))
        else:
            gw, gb = w.copy(), 0.0
        w -= lr * gw
        b -= lr * gb
    return w, b


def main() -> None:
    X, y = D.make_blobs()

    print("A 标签用 {0,1}：")
    y01 = (y > 0).astype(float)
    w, b = gd_svm(X, y01, C=1.0)
    pred = np.where(X @ w + b >= 0, 1.0, 0.0)
    print(f"   准确率 {np.mean(pred == y01):.3f}（正确标签的模型应 ≥0.95）")
    assert np.mean(pred == y01) < 0.8

    print("\nB 梯度漏乘 C：")
    margins = []
    for C in (0.1, 1.0, 10.0):
        w, b = gd_svm(X, y, C=C, ignore_C=True)
        margins.append(2.0 / np.linalg.norm(w))
    print(f"   间隔：{[round(m, 4) for m in margins]}（应随 C 增大而变小）")
    assert max(margins) - min(margins) < 1e-3

    print("\nC RBF 核用 +γ：")
    Xs = X[:50]
    good = _kernel(Xs, Xs, "rbf", 0.5, 3, 1.0)
    bad = np.exp(0.5 * ((Xs[:, None, :] - Xs[None, :, :]) ** 2).sum(-1))
    print(f"   正常核范围 [{good.min():.3f}, {good.max():.3f}]")
    print(f"   错误核范围 [{bad.min():.3e}, {bad.max():.3e}]")
    assert good.max() <= 1.0 + 1e-12 and bad.max() > 10

    # 正例：正确模型
    model = LinearSVM(C=1.0, lr=1e-3, epochs=20000, tol=1e-8, standardize=False).fit(X, y)
    print(f"\n正确实现：准确率 {np.mean(model.predict(X) == y):.3f}，间隔 {model.margin:.3f}")
    assert np.mean(model.predict(X) == y) > 0.95


if __name__ == "__main__":
    main()
