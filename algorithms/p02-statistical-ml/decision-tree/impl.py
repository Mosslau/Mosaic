"""决策树 ID3 / CART — 手写实现（监督估计器）

本文件不调 sklearn：熵、基尼、候选切分点、递归生长、代价复杂度剪枝都手写。

    tree = DecisionTree(criterion="gini", max_depth=5, min_samples_leaf=1)
    tree.fit(X_train, y_train)
    label = tree.predict(X_test)
    proba = tree.predict_proba(X_test)

节点结构（`Node` 是 dict）：
    {
        "proba": 叶子/节点上的类分布, "n": 样本数, "impurity": 不纯度,
        "value": 多数类下标, "feature"/"threshold"/"left"/"right": 内部节点才有,
    }
"""

from __future__ import annotations

import numpy as np

Node = dict


def entropy(y: np.ndarray) -> float:
    """H(D) = −Σ p_k log2 p_k；p=0 的项按 0 处理。"""
    y = np.asarray(y)
    _, counts = np.unique(y, return_counts=True)
    p = counts / counts.sum()
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p)))


def gini(y: np.ndarray) -> float:
    """Gini(D) = 1 − Σ p_k²。"""
    y = np.asarray(y)
    _, counts = np.unique(y, return_counts=True)
    p = counts / counts.sum()
    return float(1.0 - np.sum(p ** 2))


def _impurity_from_counts(counts: np.ndarray, criterion: str) -> float:
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts / total
    if criterion == "gini":
        return float(1.0 - np.sum(p ** 2))
    return float(-np.sum(p[p > 0] * np.log2(p[p > 0])))


def _leaf(proba: np.ndarray, n: int, impurity: float) -> Node:
    return {"proba": proba, "n": n, "impurity": impurity,
            "value": int(np.argmax(proba))}


class DecisionTree:
    """CART 分类树：基尼/熵 + 递归二分 + 代价复杂度剪枝（ccp_alpha）。"""

    def __init__(self, criterion: str = "gini", max_depth: int | None = None,
                 min_samples_split: int = 2, min_samples_leaf: int = 1,
                 ccp_alpha: float = 0.0) -> None:
        if criterion not in ("gini", "entropy"):
            raise ValueError("criterion 只支持 gini / entropy")
        if max_depth is not None and max_depth < 1:
            raise ValueError("max_depth 至少为 1（或 None）")
        if min_samples_split < 2:
            raise ValueError("min_samples_split 至少为 2")
        if min_samples_leaf < 1:
            raise ValueError("min_samples_leaf 至少为 1")
        if ccp_alpha < 0:
            raise ValueError("ccp_alpha 不能为负")
        self.criterion = criterion
        self.max_depth = max_depth
        self.min_samples_split = int(min_samples_split)
        self.min_samples_leaf = int(min_samples_leaf)
        self.ccp_alpha = float(ccp_alpha)
        self.root: Node | None = None
        self.classes_: np.ndarray | None = None
        self.n_features_in_: int | None = None
        self._importances: np.ndarray | None = None

    # ------------------------------------------------------------ 建树

    def fit(self, X: np.ndarray, y: np.ndarray) -> DecisionTree:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 2:
            raise ValueError(f"X 必须是二维，实际 {X.shape}")
        if y.ndim != 1:
            raise ValueError(f"y 必须是一维，实际 {y.shape}")
        if len(X) != len(y):
            raise ValueError(f"样本数不一致：{len(X)} vs {len(y)}")
        if len(X) == 0:
            raise ValueError("样本数为 0")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        self.classes_, y_idx = np.unique(y, return_inverse=True)
        self.n_features_in_ = X.shape[1]
        self._importances = np.zeros(X.shape[1])
        self.root = self._grow(X, y_idx, depth=0)
        if self.ccp_alpha > 0:
            self._prune(self.root, self.ccp_alpha)
        self._compute_importances(self.root)
        return self

    def _grow(self, X: np.ndarray, y: np.ndarray, depth: int) -> Node:
        counts = np.bincount(y, minlength=len(self.classes_)).astype(float)
        proba = counts / counts.sum()
        impurity = _impurity_from_counts(counts, self.criterion)
        node = _leaf(proba, len(y), impurity)

        if (impurity == 0.0
                or len(y) < self.min_samples_split
                or (self.max_depth is not None and depth >= self.max_depth)):
            return node

        split = self._best_split(X, y)
        if split is None:
            return node

        feature, threshold, left_mask = split
        node["feature"] = feature
        node["threshold"] = float(threshold)
        node["left"] = self._grow(X[left_mask], y[left_mask], depth + 1)
        node["right"] = self._grow(X[~left_mask], y[~left_mask], depth + 1)
        return node

    def _best_split(self, X: np.ndarray, y: np.ndarray):
        n, n_features = X.shape
        n_classes = len(self.classes_)
        Y = np.zeros((n, n_classes))
        Y[np.arange(n), y] = 1.0
        parent = _impurity_from_counts(Y.sum(axis=0), self.criterion)
        best_gain, best = -1.0, None

        for f in range(n_features):
            order = np.argsort(X[:, f], kind="mergesort")
            xs = X[order, f]
            cum = np.cumsum(Y[order], axis=0)          # 左侧各类计数
            total = cum[-1]
            for i in range(n - 1):
                if xs[i] == xs[i + 1]:
                    continue
                if i + 1 < self.min_samples_leaf or n - i - 1 < self.min_samples_leaf:
                    continue
                left_counts = cum[i]
                right_counts = total - left_counts
                w_left, w_right = (i + 1) / n, (n - i - 1) / n
                child = (w_left * _impurity_from_counts(left_counts, self.criterion)
                         + w_right * _impurity_from_counts(right_counts, self.criterion))
                gain = parent - child
                if gain > best_gain + 1e-12:
                    best_gain = gain
                    best = (f, float((xs[i] + xs[i + 1]) / 2.0),
                            X[:, f] <= (xs[i] + xs[i + 1]) / 2.0)
        return best

    # ------------------------------------------------------------ 剪枝

    def _risk(self, node: Node) -> float:
        return node["n"] / self._n_total * node["impurity"]

    def _leaves(self, node: Node) -> int:
        if "feature" not in node:
            return 1
        return self._leaves(node["left"]) + self._leaves(node["right"])

    def _subtree_risk(self, node: Node) -> float:
        if "feature" not in node:
            return self._risk(node)
        return self._subtree_risk(node["left"]) + self._subtree_risk(node["right"])

    def _make_leaf(self, node: Node) -> Node:
        return _leaf(node["proba"], node["n"], node["impurity"])

    def _prune(self, node: Node, alpha: float) -> bool:
        """自底向上：若某内部节点的有效 α ≤ 阈值，就剪成叶子。返回是否剪过。"""
        if "feature" not in node:
            return False
        changed = self._prune(node["left"], alpha)
        changed = self._prune(node["right"], alpha) or changed
        if "feature" not in node:
            return changed
        leaves = self._leaves(node)
        if leaves <= 1:
            return changed
        eff = (self._risk(node) - self._subtree_risk(node)) / (leaves - 1)
        if eff <= alpha + 1e-12:
            leaf = self._make_leaf(node)
            node.clear()
            node.update(leaf)
            return True
        return changed

    @property
    def _n_total(self) -> int:
        return self.root["n"]

    # ------------------------------------------------------------ 预测

    def _leaf_for(self, row: np.ndarray) -> Node:
        node = self.root
        while "feature" in node:
            node = node["left"] if row[node["feature"]] <= node["threshold"] else node["right"]
        return node

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.root is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.n_features_in_:
            raise ValueError(f"X 形状应为 (n, {self.n_features_in_})，实际 {X.shape}")
        return np.vstack([self._leaf_for(row)["proba"] for row in X])

    def predict(self, X: np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        return self.classes_[np.argmax(proba, axis=1)]

    def apply(self, X: np.ndarray) -> np.ndarray:
        """返回每个样本落到的叶子编号（按先序给叶子编号）。"""
        if self.root is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        ids: dict[int, int] = {}

        def number(node: Node) -> None:
            if "feature" not in node:
                ids[id(node)] = len(ids)
                return
            number(node["left"])
            number(node["right"])

        number(self.root)
        out = []
        for row in X:
            node = self.root
            while "feature" in node:
                node = node["left"] if row[node["feature"]] <= node["threshold"] else node["right"]
            out.append(ids[id(node)])
        return np.array(out, dtype=int)

    # ------------------------------------------------------------ 结构

    def get_depth(self) -> int:
        def depth(node: Node) -> int:
            if "feature" not in node:
                return 0
            return 1 + max(depth(node["left"]), depth(node["right"]))
        return depth(self.root)

    def get_n_leaves(self) -> int:
        return self._leaves(self.root)

    def _compute_importances(self, node: Node) -> float:
        """返回子树的加权不纯度下降总和，写回 self._importances。"""
        if "feature" not in node:
            return 0.0
        n = node["n"]
        left, right = node["left"], node["right"]
        child_imp = (left["n"] / n) * left["impurity"] + (right["n"] / n) * right["impurity"]
        gain = node["impurity"] - child_imp
        self._importances[node["feature"]] += n * gain
        self._compute_importances(left)
        self._compute_importances(right)
        return gain

    @property
    def feature_importances_(self) -> np.ndarray:
        if self._importances is None:
            raise RuntimeError("模型尚未训练")
        total = self._importances.sum()
        return self._importances / total if total > 0 else self._importances


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
