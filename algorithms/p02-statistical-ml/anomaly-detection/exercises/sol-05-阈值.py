"""参考解：第 5 题（迁移）——阈值与 F1

    uv run python sol-05-阈值.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.metrics import precision_score, recall_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import IsolationForest  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    normal, anomaly = X[y == 0], X[y != 0]
    X_tr = normal[:120]
    X_te = np.vstack([normal[120:], anomaly[:100]])
    y_te = np.r_[np.zeros(len(normal) - 120), np.ones(100)]

    print(f"{'contam':>7} | {'精确率':>6} | {'召回率':>6} | {'F1':>6}")
    print("-" * 32)
    best = None
    for c in (0.01, 0.02, 0.05, 0.1, 0.2):
        m = IsolationForest(contamination=c, random_state=0).fit(X_tr)
        pred = (m.score_samples(X_te) > m.threshold_).astype(int)
        p = precision_score(y_te, pred, zero_division=0)
        r = recall_score(y_te, pred, zero_division=0)
        f1 = 0.0 if p + r == 0 else 2 * p * r / (p + r)
        print(f"{c:7.2f} | {p:6.3f} | {r:6.3f} | {f1:6.3f}")
        if best is None or f1 > best[1]:
            best = (c, f1)
    print(f"\nF1 最优：contamination={best[0]}，F1={best[1]:.3f}")
    assert best[1] >= 0.9
    print("→ AUC 只看排序；F1 依赖阈值，必须按业务/验证集选 contamination。")


if __name__ == "__main__":
    main()
