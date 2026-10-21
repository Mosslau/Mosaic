"""参考解：第 5 题（迁移）——RBF 的 γ 交叉验证

    uv run python sol-05-gamma.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import KFold

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import KernelSVM  # noqa: E402


def cv_accuracy(gamma: float, X, y, C: float = 10.0, k: int = 5) -> float:
    scores = []
    for train, val in KFold(n_splits=k, shuffle=True, random_state=0).split(X):
        model = KernelSVM(C=C, kernel="rbf", gamma=gamma, max_iter=100, tol=1e-4,
                          standardize=False).fit(X[train], y[train])
        scores.append(float(np.mean(model.predict(X[val]) == y[val])))
    return float(np.mean(scores))


def main() -> None:
    X, y = D.make_circles()
    gammas = (0.01, 0.1, 0.5, 1.0, 5.0)
    print(f"{'gamma':>7} | {'5 折 CV acc':>10}")
    print("-" * 24)
    cv = {}
    for g in gammas:
        cv[g] = cv_accuracy(g, X, y)
        print(f"{g:7.2f} | {cv[g]:10.3f}")

    best_g = max(cv, key=cv.get)
    print(f"\n最优 γ = {best_g}（CV {cv[best_g]:.3f}）")
    assert cv[best_g] >= 0.95, "最优 γ 的 CV 应 ≥ 0.95"
    assert cv[0.01] < 0.75, "γ 太小时应接近线性"

    final = KernelSVM(C=10.0, kernel="rbf", gamma=best_g, max_iter=150, tol=1e-4,
                      standardize=False).fit(X, y)
    too_large = KernelSVM(C=10.0, kernel="rbf", gamma=5.0, max_iter=150, tol=1e-4,
                          standardize=False).fit(X, y)
    print(f"最终模型：训练准确率 {np.mean(final.predict(X) == y):.3f}，"
          f"支持向量 {final.n_support}")
    print(f"γ=5：支持向量 {too_large.n_support}（模型更复杂；本数据太容易，CV 仍是 1.0）")
    assert too_large.n_support > final.n_support, "γ 过大时支持向量应变多"


if __name__ == "__main__":
    main()
