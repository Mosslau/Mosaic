"""参考解：第 5 题（迁移）——深度与不稳定性

    uv run python sol-05-稳定性.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import DecisionTree  # noqa: E402
from sklearn.datasets import make_moons  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402


def disagreement(depth: int, boot: int = 20) -> float:
    X, y = make_moons(n_samples=300, noise=0.5, random_state=0)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
    rng = np.random.default_rng(0)
    preds = []
    for _ in range(boot):
        idx = rng.integers(0, len(y_tr), len(y_tr))
        tree = DecisionTree(max_depth=depth).fit(X_tr[idx], y_tr[idx])
        preds.append(tree.predict(X_te))
    preds = np.array(preds)
    return float(np.mean([np.mean(preds[i] != preds[j])
                          for i in range(boot) for j in range(i + 1, boot)]))


def main() -> None:
    d2 = disagreement(2)
    d8 = disagreement(8)
    print(f"depth=2 的两两分歧：{d2:.4f}")
    print(f"depth=8 的两两分歧：{d8:.4f}")
    assert d8 > d2 + 0.05, "深树应对样本扰动更敏感"
    print("\n→ 深树切分更多、方差更大；这是随机森林 bagging 的动机。")


if __name__ == "__main__":
    main()
