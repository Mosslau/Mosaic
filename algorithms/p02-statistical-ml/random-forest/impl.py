"""随机森林 — 手写实现（监督估计器）

随机森林 = 决策树的 bagging 集成。本文件自带一棵精简 CART（`_Tree`），
这样单棵树与森林共享同一套划分逻辑，不需要跨目录 import。

    forest = RandomForest(n_trees=100, max_features="sqrt", random_state=0)
    forest.fit(X_train, y_train)
    label = forest.predict(X_test)
    proba = forest.predict_proba(X_test)
    forest.oob_score_          # 训练时算好的袋外精度

随机性的两个来源：
1. bootstrap：每棵树在同规模的自助采样集上训练（约 36.8% 样本未入袋）；
2. feature subsampling：每次划分只从随机特征子集里选最优。
"""

from __future__ import annotations

import numpy as np

Node = dict


def _gini_from_counts(counts: np.ndarray) -> float:
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts / total
    return float(1.0 - np.sum(p ** 2))


class _Tree:
    """精简 CART：gini + 每次划分随机选 max_features 个特征。"""

    def __init__(self, n_features: int, n_classes: int, max_features: int,
                 max_depth: int | None, min_samples_leaf: int,
                 rng: np.random.Generator) -> None:
        self.n_features = n_features
        self.n_classes = n_classes
        self.max_features = max_features
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.rng = rng
        self.root: Node | None = None
        self._importances = np.zeros(n_features)

    def fit(self, X: np.ndarray, y: np.ndarray) -> _Tree:
        self._n_total = len(y)
        self.root = self._grow(X, y, depth=0)
        return self

    def _grow(self, X: np.ndarray, y: np.ndarray, depth: int) -> Node:
        counts = np.bincount(y, minlength=self.n_classes).astype(float)
        proba = counts / counts.sum()
        impurity = _gini_from_counts(counts)
        node = {"proba": proba, "n": len(y), "impurity": impurity,
                "value": int(np.argmax(proba))}
        if (impurity == 0.0 or len(y) < 2 * self.min_samples_leaf
                or (self.max_depth is not None and depth >= self.max_depth)):
            return node

        split = self._best_split(X, y)
        if split is None:
            return node
        feature, threshold, left_mask = split
        node.update(feature=feature, threshold=threshold)
        node["left"] = self._grow(X[left_mask], y[left_mask], depth + 1)
        node["right"] = self._grow(X[~left_mask], y[~left_mask], depth + 1)
        return node

    def _best_split(self, X: np.ndarray, y: np.ndarray):
        n = len(y)
        Y = np.zeros((n, self.n_classes))
        Y[np.arange(n), y] = 1.0
        parent = _gini_from_counts(Y.sum(axis=0))
        features = self.rng.choice(self.n_features, size=self.max_features, replace=False)
        best_gain, best = -1.0, None
        for f in features:
            order = np.argsort(X[:, f], kind="mergesort")
            xs = X[order, f]
            cum = np.cumsum(Y[order], axis=0)
            for i in range(n - 1):
                if xs[i] == xs[i + 1]:
                    continue
                if i + 1 < self.min_samples_leaf or n - i - 1 < self.min_samples_leaf:
                    continue
                left = cum[i]
                right = cum[-1] - left
                child = ((i + 1) / n) * _gini_from_counts(left) + \
                        ((n - i - 1) / n) * _gini_from_counts(right)
                gain = parent - child
                if gain > best_gain + 1e-12:
                    best_gain = gain
                    t = float((xs[i] + xs[i + 1]) / 2.0)
                    best = (int(f), t, X[:, f] <= t)
        if best is not None:
            self._importances[best[0]] += n * best_gain
        return best

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        out = np.empty((len(X), self.n_classes))
        for i, row in enumerate(X):
            node = self.root
            while "feature" in node:
                node = node["left"] if row[node["feature"]] <= node["threshold"] else node["right"]
            out[i] = node["proba"]
        return out

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)

    @property
    def feature_importances_(self) -> np.ndarray:
        total = self._importances.sum()
        return self._importances / total if total > 0 else self._importances


class RandomForest:
    """由 n_trees 棵决策树组成的 bagging 集成（分类，多数投票/概率平均）。"""

    def __init__(self, n_trees: int = 100, max_features: str | int | float | None = "sqrt",
                 max_depth: int | None = None, min_samples_leaf: int = 1,
                 random_state: int | None = None) -> None:
        if n_trees < 1:
            raise ValueError("n_trees 至少为 1")
        if max_depth is not None and max_depth < 1:
            raise ValueError("max_depth 至少为 1（或 None）")
        if min_samples_leaf < 1:
            raise ValueError("min_samples_leaf 至少为 1")
        if not (max_features is None or max_features in ("sqrt", "log2")
                or isinstance(max_features, (int, float))):
            raise ValueError("max_features 只支持 None / sqrt / log2 / int / float")
        if isinstance(max_features, (int, float)) and not isinstance(max_features, bool) \
                and max_features <= 0:
            raise ValueError("max_features 为正数")
        self.n_trees = int(n_trees)
        self.max_features = max_features
        self.max_depth = max_depth
        self.min_samples_leaf = int(min_samples_leaf)
        self.random_state = random_state
        self.trees: list[_Tree] = []
        self.classes_: np.ndarray | None = None
        self.n_features_in_: int | None = None
        self.oob_score_: float | None = None
        self.oob_decision_function_: np.ndarray | None = None
        self._oob_masks: list[np.ndarray] = []
        self._n_train: int = 0

    def _resolve_max_features(self, p: int) -> int:
        mf = self.max_features
        if mf is None:
            return p
        if mf == "sqrt":
            return max(1, int(np.sqrt(p)))
        if mf == "log2":
            return max(1, int(np.log2(p)))
        if isinstance(mf, float):
            return max(1, min(p, int(p * mf)))
        return max(1, min(p, int(mf)))

    def fit(self, X: np.ndarray, y: np.ndarray) -> RandomForest:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 2:
            raise ValueError(f"X 必须是二维，实际 {X.shape}")
        if y.ndim != 1 or len(X) != len(y):
            raise ValueError("X / y 长度或维度不匹配")
        if len(X) == 0:
            raise ValueError("样本数为 0")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")

        self.classes_, y_idx = np.unique(y, return_inverse=True)
        self.n_features_in_ = X.shape[1]
        self._n_train = len(y)
        n_features = X.shape[1]
        m = self._resolve_max_features(n_features)
        rng = np.random.default_rng(self.random_state)

        self.trees = []
        self._oob_masks = []
        for _ in range(self.n_trees):
            idx = rng.integers(0, len(y), len(y))
            in_bag = np.zeros(len(y), dtype=bool)
            in_bag[idx] = True
            tree = _Tree(n_features, len(self.classes_), m, self.max_depth,
                         self.min_samples_leaf, rng).fit(X[idx], y_idx[idx])
            self.trees.append(tree)
            self._oob_masks.append(~in_bag)

        self._compute_oob(X, y_idx)
        return self

    def _compute_oob(self, X: np.ndarray, y_idx: np.ndarray) -> None:
        n, k = len(X), len(self.classes_)
        proba_sum = np.zeros((n, k))
        counts = np.zeros(n)
        for tree, mask in zip(self.trees, self._oob_masks):
            if not np.any(mask):
                continue
            proba_sum[mask] += tree.predict_proba(X[mask])
            counts[mask] += 1
        valid = counts > 0
        self.oob_decision_function_ = np.full((n, k), np.nan)
        self.oob_decision_function_[valid] = proba_sum[valid] / counts[valid, None]
        self.oob_score_ = float(np.mean(np.argmax(self.oob_decision_function_[valid], axis=1)
                                        == y_idx[valid])) if np.any(valid) else float("nan")

    def oob_score(self, X: np.ndarray, y: np.ndarray) -> float:
        """用训练时记录的未入袋掩码重算 OOB 精度（X/y 必须是训练集）。"""
        if self.classes_ is None:
            raise RuntimeError("模型尚未训练")
        if len(X) != self._n_train:
            raise ValueError("oob_score 只对训练集有效")
        _, y_idx = np.unique(y, return_inverse=True)
        if len(y_idx) != self._n_train:
            raise ValueError("y 长度与训练集不一致")
        n, k = len(X), len(self.classes_)
        proba_sum = np.zeros((n, k))
        counts = np.zeros(n)
        for tree, mask in zip(self.trees, self._oob_masks):
            proba_sum[mask] += tree.predict_proba(np.asarray(X, dtype=float)[mask])
            counts[mask] += 1
        valid = counts > 0
        pred = np.argmax(proba_sum[valid] / counts[valid, None], axis=1)
        return float(np.mean(pred == y_idx[valid]))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.trees:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.n_features_in_:
            raise ValueError(f"X 形状应为 (n, {self.n_features_in_})，实际 {X.shape}")
        proba = np.zeros((len(X), len(self.classes_)))
        for tree in self.trees:
            proba += tree.predict_proba(X)
        return proba / len(self.trees)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]

    @property
    def feature_importances_(self) -> np.ndarray:
        if not self.trees:
            raise RuntimeError("模型尚未训练")
        imp = np.mean([t.feature_importances_ for t in self.trees], axis=0)
        total = imp.sum()
        return imp / total if total > 0 else imp


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
