"""参考解：第 4 题（实现）——基于验证集的剪枝（REP）

    uv run python sol-04-REP.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import DecisionTree, _leaf  # noqa: E402


def acc(model, X, y) -> float:
    return float(np.mean(model.predict(X) == y))


def rep_prune(tree, X_val, y_val) -> None:
    """自底向上：剪掉不提升验证准确率的子树。"""
    def walk(node):
        if "feature" not in node:
            return
        walk(node["left"])
        walk(node["right"])
        if "feature" not in node:
            return
        before = acc(tree, X_val, y_val)
        saved = dict(node)
        leaf = _leaf(node["proba"], node["n"], node["impurity"])
        node.clear()
        node.update(leaf)
        if acc(tree, X_val, y_val) + 1e-12 >= before:
            return                      # 保留剪枝
        node.clear()
        node.update(saved)              # 恢复

    walk(tree.root)


def main() -> None:
    X_tr, X_tmp, y_tr, y_tmp = D.make_data()
    X_val, X_te, y_val, y_te = train_test_split(X_tmp, y_tmp, test_size=0.5,
                                                random_state=0, stratify=y_tmp)
    print(f"train {len(y_tr)} / val {len(y_val)} / test {len(y_te)}")

    full = DecisionTree().fit(X_tr, y_tr)
    base = (acc(full, X_val, y_val), acc(full, X_te, y_te), full.get_n_leaves())
    rep_prune(full, X_val, y_val)
    after = (acc(full, X_val, y_val), acc(full, X_te, y_te), full.get_n_leaves())

    print(f"{'':6} | {'验证 acc':>8} | {'测试 acc':>8} | {'叶子':>4}")
    print("-" * 34)
    print(f"{'剪枝前':6} | {base[0]:8.4f} | {base[1]:8.4f} | {base[2]:4d}")
    print(f"{'剪枝后':6} | {after[0]:8.4f} | {after[1]:8.4f} | {after[2]:4d}")

    assert after[2] < base[2], "REP 应减少叶子"
    assert after[0] >= base[0] - 1e-12, "验证准确率不应下降"
    assert after[1] >= base[1] - 0.02, "测试准确率不应比完全树差 2 个百分点以上"
    print("\n→ REP 用验证集换掉了一部分枝叶，验证不降、测试基本持平。")


if __name__ == "__main__":
    main()
