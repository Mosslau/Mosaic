"""参考解：第 4 题（实现）——置换重要性

    uv run python sol-04-置换重要性.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import RandomForest  # noqa: E402


def permutation_importance(model, X, y, repeats=5, seed=0):
    rng = np.random.default_rng(seed)
    base = float(np.mean(model.predict(X) == y))
    drops = np.zeros(X.shape[1])
    for j in range(X.shape[1]):
        vals = []
        for _ in range(repeats):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            vals.append(base - float(np.mean(model.predict(Xp) == y)))
        drops[j] = np.mean(vals)
    return drops


def main() -> None:
    X_tr, X_te, y_tr, y_te = D.make_high_dim()
    forest = RandomForest(n_trees=100, random_state=0).fit(X_tr, y_tr)
    perm = permutation_importance(forest, X_te, y_te)
    imp = forest.feature_importances_
    order_p = np.argsort(-perm)
    order_i = np.argsort(-imp)
    print(f"{'rank':>4} | {'置换':>16} | {'不纯度':>16}")
    print("-" * 44)
    for r in range(6):
        j, k = order_p[r], order_i[r]
        print(f"{r + 1:4d} | x{j:<3} {perm[j]:7.4f}      | x{k:<3} {imp[k]:7.4f}")

    top4 = set(order_p[:4].tolist())
    print(f"\n置换重要性前 4：{sorted(top4)}；不纯度前 4：{sorted(order_i[:4].tolist())}")
    assert top4 == {0, 1, 2, 3}, "真特征应占据置换重要性前 4"
    assert np.mean(perm[:4]) > 2 * np.mean(perm[4:]), "真特征的下降应明显大于噪声"
    print("\n→ 置换重要性把'真特征'挑了出来，与不纯度重要性同向；相关特征会互相分摊。")


if __name__ == "__main__":
    main()
