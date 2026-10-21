"""参考解：第 3 题（判断）——三个随机森林 bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import RandomForest  # noqa: E402


def disagreement(preds: np.ndarray) -> float:
    n = len(preds)
    return float(np.mean([np.mean(preds[i] != preds[j])
                          for i in range(n) for j in range(i + 1, n)]))


def main() -> None:
    rng = np.random.default_rng(0)
    n = 100
    idx = rng.choice(n, n, replace=False)
    mask = np.ones(n, dtype=bool)
    mask[idx] = False
    print("A 无放回抽样：")
    print(f"   OOB 比例 {mask.mean():.3f}（正确 bootstrap 应约 0.368）")
    assert mask.mean() == 0.0

    X_tr, X_te, y_tr, y_te = D.make_moons_data()
    print("\nB 特征随机失效（每棵树固定特征子集 ≈ max_features=None）：")
    a = RandomForest(n_trees=20, max_features=None, random_state=0).fit(X_tr, y_tr)
    b = RandomForest(n_trees=20, max_features="sqrt", random_state=0).fit(X_tr, y_tr)
    da = disagreement(np.array([t.predict(X_te) for t in a.trees]))
    db = disagreement(np.array([t.predict(X_te) for t in b.trees]))
    print(f"   max_features=None 的分歧 {da:.3f}；sqrt 的分歧 {db:.3f}")
    assert da < db, "特征随机应让树更不一致"

    print("\nC OOB 把入袋树也算进去：")
    forest = RandomForest(n_trees=100, random_state=0).fit(X_tr, y_tr)
    all_tree = float(np.mean(forest.predict(X_tr) == y_tr))
    oob = float(forest.oob_score_)
    test = D.accuracy(y_te, forest.predict(X_te))
    print(f"   全树平均（训练）{all_tree:.3f}；正确 OOB {oob:.3f}；测试 {test:.3f}")
    assert all_tree > oob + 0.02, "全树平均会明显比 OOB 乐观"

    print("\n→ A 没有 OOB；B 树太像；C 的 OOB 被训练样本污染。")


if __name__ == "__main__":
    main()
