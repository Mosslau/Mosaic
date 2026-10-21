"""参考解：第 4 题（实现）——多项式核解 XOR

    uv run python sol-04-多项式核.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import KernelSVM  # noqa: E402

X = np.array([[-1.0, -1.0], [1.0, 1.0], [-1.0, 1.0], [1.0, -1.0]])
y = np.array([-1.0, -1.0, 1.0, 1.0])


def accuracy(model) -> float:
    return float(np.mean(model.predict(X) == y))


def main() -> None:
    print(f"{'degree':>6} | {'手写 acc':>8} | {'sklearn acc':>11}")
    print("-" * 32)
    accs = {}
    for degree in (1, 2, 3):
        hand = KernelSVM(C=10.0, kernel="poly", degree=degree, coef0=1.0, gamma=1.0,
                         max_iter=200, tol=1e-5, standardize=False).fit(X, y)
        from sklearn.svm import SVC
        sk = SVC(C=10.0, kernel="poly", degree=degree, coef0=1.0, gamma=1.0).fit(X, y)
        a, b = accuracy(hand), float(np.mean(sk.predict(X) == y))
        accs[degree] = (a, b)
        print(f"{degree:>6} | {a:8.2f} | {b:11.2f}")

    assert accs[1][0] <= 0.75, "一次多项式（线性）分不开 XOR"
    assert accs[2][0] == 1.0 and accs[2][1] == 1.0, "二次多项式应能分开 XOR"
    print("\n→ 二次核把特征扩展到 x1·x2，XOR 就线性可分了。")


if __name__ == "__main__":
    main()
