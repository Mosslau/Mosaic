"""决策树 ID3 / CART — 框架对照（监督估计器）

对照对象：sklearn `DecisionTreeClassifier`。
口径：同一份数据、同一 `criterion`、同一 `max_depth` / `ccp_alpha`，比较
准确率、叶子数、深度与耗时。sklearn 额外做了预排序/分箱、缺失值支持、
多输出与并行，这些不改变本实验的划分准则。
"""

from __future__ import annotations

from sklearn.tree import DecisionTreeClassifier


def fit_tree(X, y, criterion: str = "gini", max_depth: int | None = None,
             min_samples_leaf: int = 1, ccp_alpha: float = 0.0) -> DecisionTreeClassifier:
    return DecisionTreeClassifier(
        criterion=criterion, max_depth=max_depth, min_samples_leaf=min_samples_leaf,
        ccp_alpha=ccp_alpha, random_state=0).fit(X, y)


def pruning_path(X, y, criterion: str = "gini") -> tuple:
    """sklearn 的代价复杂度剪枝路径：返回 (alphas, impurities)。"""
    clf = DecisionTreeClassifier(criterion=criterion, random_state=0).fit(X, y)
    path = clf.cost_complexity_pruning_path(X, y)
    return path.ccp_alphas, path.impurities


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
