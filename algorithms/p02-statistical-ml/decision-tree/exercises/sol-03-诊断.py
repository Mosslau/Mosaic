"""参考解：第 3 题（判断）——三个决策树 bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import DecisionTree, entropy  # noqa: E402


def entropy_bad(y, n_classes=3):
    counts = np.bincount(y, minlength=n_classes)
    p = counts / counts.sum()
    return float(-np.sum(p * np.log2(p)))          # bug：p=0 时 log2(0)


def main() -> None:
    y = np.array([0, 0, 1])
    print("A 不处理 p=0：")
    print(f"   正确 entropy = {entropy(y):.4f}；错误版 = {entropy_bad(y):.4f}")
    assert np.isnan(entropy_bad(y)) and np.isfinite(entropy(y))

    print("\nB 允许空孩子：")
    X = np.array([[0.0], [1.0], [2.0], [3.0]])
    yb = np.array([0, 0, 1, 1])
    threshold = X[:, 0].min() - 1.0
    left = X[:, 0] <= threshold
    print(f"   阈值 {threshold}：左子集 {left.sum()} 个、右子集 {(~left).sum()} 个")
    assert left.sum() == 0, "这个切分制造了空左孩子"
    tree = DecisionTree().fit(X, yb)
    assert tree.get_n_leaves() == 2, "正确实现不会产生空孩子"

    print("\nC α 分母用叶子数：")
    X, yc = np.random.default_rng(0).normal(size=(200, 3)), None
    yc = (X[:, 0] + X[:, 1] > 0).astype(int)
    tree = DecisionTree().fit(X, yc)
    full = tree.get_n_leaves()
    # 用同一棵树手动算两种 α（这里只比较公式，不实际剪）
    root = tree.root
    n_total = root["n"]

    def risk(node):
        return node["n"] / n_total * node["impurity"]

    def sub_risk(node):
        if "feature" not in node:
            return risk(node)
        return sub_risk(node["left"]) + sub_risk(node["right"])

    def leaves(node):
        return 1 if "feature" not in node else leaves(node["left"]) + leaves(node["right"])

    lv = leaves(root)
    alpha_good = (risk(root) - sub_risk(root)) / (lv - 1)
    alpha_bad = (risk(root) - sub_risk(root)) / lv
    print(f"   完全树 {full} 叶；α_good={alpha_good:.4f}，α_bad={alpha_bad:.4f}")
    assert alpha_bad < alpha_good
    print("\n→ A 出 nan；B 产生空孩子；C 的 α 偏小、剪枝不足。")


if __name__ == "__main__":
    main()
