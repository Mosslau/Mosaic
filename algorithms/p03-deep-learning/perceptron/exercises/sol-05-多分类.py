"""参考解：第 5 题（迁移）——一对多感知机

    uv run python sol-05-多分类.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import Perceptron  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    keep = np.isin(y, [0, 1, 2])
    X, y = X[keep], y[keep]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
    scaler = StandardScaler().fit(X_tr)
    X_tr, X_te = scaler.transform(X_tr), scaler.transform(X_te)

    models = {}
    for c in (0, 1, 2):
        yy = np.where(y_tr == c, 1, -1)
        models[c] = Perceptron(lr=0.01, epochs=50, random_state=0).fit(X_tr, yy)

    scores = np.column_stack([models[c].decision_function(X_te) for c in (0, 1, 2)])
    pred = scores.argmax(axis=1)
    acc = float(np.mean(pred == y_te))
    log = LogisticRegression(max_iter=5000).fit(X_tr, y_tr)
    log_acc = float(np.mean(log.predict(X_te) == y_te))
    print(f"一对多感知机：acc {acc:.4f}")
    print(f"逻辑回归：    acc {log_acc:.4f}")
    assert acc >= 0.9
    print("\n→ 多分类靠“每类一个二分类器 + 分数最大”；感知机没有概率，只能比分数。")


if __name__ == "__main__":
    main()
