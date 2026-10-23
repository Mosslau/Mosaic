"""Boosting / GBDT — 手写实现（监督估计器，回归）

梯度提升 = 加法模型 + 残差拟合：

    F_0(x) = mean(y)
    r_i    = y_i − F_{m−1}(x_i)          # 负梯度（平方损失下就是残差）
    F_m(x) = F_{m−1}(x) + lr · h_m(x)    # h_m 拟合残差

    model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1)
    model.fit(X, y, eval_set=(X_val, y_val), early_stopping_rounds=10)
    pred = model.predict(X_test)

本文件不调 sklearn：回归树（MSE 划分）、残差、学习率、早停都手写。
AdaBoost 是它的前身（样本重加权 + 弱分类器投票），本实验聚焦 GBDT 的
"加法 + 残差"主线，AdaBoost 在 README 里作为历史对照说明。
"""

from __future__ import annotations

import numpy as np

Node = dict


class _RegTree:
    """CART 回归树：MSE 划分，叶子取均值。"""

    def __init__(self, max_depth: int = 3, min_samples_leaf: int = 1) -> None:
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.root: Node | None = None
        self._importances: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> _RegTree:
        self._n_features = X.shape[1]
        self._importances = np.zeros(self._n_features)
        self.root = self._grow(X, y, depth=0)
        return self

    def _grow(self, X: np.ndarray, y: np.ndarray, depth: int) -> Node:
        node = {"value": float(np.mean(y)), "n": len(y),
                "sse": float(np.sum((y - y.mean()) ** 2))}
        if (depth >= self.max_depth or len(y) < 2 * self.min_samples_leaf
                or node["sse"] <= 1e-12):
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
        n, p = X.shape
        total = float(y.sum())
        total_sq = float(np.sum(y ** 2))
        parent_sse = total_sq - total * total / n
        best_gain, best = -1.0, None
        for f in range(p):
            order = np.argsort(X[:, f], kind="mergesort")
            xs, ys = X[order, f], y[order]
            csum = np.cumsum(ys)
            csq = np.cumsum(ys ** 2)
            for i in range(n - 1):
                if xs[i] == xs[i + 1]:
                    continue
                n_l = i + 1
                n_r = n - n_l
                if n_l < self.min_samples_leaf or n_r < self.min_samples_leaf:
                    continue
                s_l, sq_l = csum[i], csq[i]
                s_r, sq_r = total - s_l, total_sq - sq_l
                sse = (sq_l - s_l * s_l / n_l) + (sq_r - s_r * s_r / n_r)
                gain = parent_sse - sse
                if gain > best_gain + 1e-12:
                    best_gain = gain
                    t = float((xs[i] + xs[i + 1]) / 2.0)
                    best = (int(f), t, X[:, f] <= t)
        if best is not None:
            self._importances[best[0]] += best_gain
        return best

    def predict(self, X: np.ndarray) -> np.ndarray:
        out = np.empty(len(X))
        for i, row in enumerate(X):
            node = self.root
            while "feature" in node:
                node = node["left"] if row[node["feature"]] <= node["threshold"] else node["right"]
            out[i] = node["value"]
        return out

    @property
    def feature_importances_(self) -> np.ndarray:
        total = self._importances.sum()
        return self._importances / total if total > 0 else self._importances


class GradientBoostingRegressor:
    """平方损失的 GBDT：残差拟合 + 学习率 + 可选早停。"""

    def __init__(self, n_estimators: int = 100, learning_rate: float = 0.1,
                 max_depth: int = 3, min_samples_leaf: int = 1,
                 subsample: float = 1.0, random_state: int | None = None) -> None:
        if n_estimators < 1:
            raise ValueError("n_estimators 至少为 1")
        if not np.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate 必须为正")
        if max_depth < 1:
            raise ValueError("max_depth 至少为 1")
        if min_samples_leaf < 1:
            raise ValueError("min_samples_leaf 至少为 1")
        if not (0 < subsample <= 1):
            raise ValueError("subsample 必须在 (0, 1]")
        self.n_estimators = int(n_estimators)
        self.learning_rate = float(learning_rate)
        self.max_depth = int(max_depth)
        self.min_samples_leaf = int(min_samples_leaf)
        self.subsample = float(subsample)
        self.random_state = random_state
        self.trees: list[_RegTree] = []
        self.baseline_: float = 0.0
        self.train_score_: list[float] = []
        self.val_score_: list[float] = []
        self.best_iteration_: int | None = None
        self.feature_importances_: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray, eval_set=None,
            early_stopping_rounds: int | None = None) -> GradientBoostingRegressor:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim != 2 or y.ndim != 1 or len(X) != len(y):
            raise ValueError("X / y 形状不匹配")
        if len(X) == 0:
            raise ValueError("样本数为 0")
        if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
            raise ValueError("X / y 含 NaN 或 inf")

        rng = np.random.default_rng(self.random_state)
        self.trees = []
        self.train_score_ = []
        self.val_score_ = []
        self.best_iteration_ = None
        self.baseline_ = float(np.mean(y))
        F = np.full(len(y), self.baseline_)
        F_val = None
        if eval_set is not None:
            X_val, y_val = eval_set
            X_val = np.asarray(X_val, dtype=float)
            y_val = np.asarray(y_val, dtype=float)
            if X_val.ndim != 2 or X_val.shape[1] != X.shape[1] or len(X_val) != len(y_val):
                raise ValueError("eval_set 形状不匹配")
            F_val = np.full(len(y_val), self.baseline_)

        best_val = float("inf")
        best_iter = 0
        since_improved = 0

        for m in range(self.n_estimators):
            residual = y - F
            if self.subsample < 1.0:
                idx = rng.choice(len(y), max(1, int(len(y) * self.subsample)),
                                 replace=False)
                tree = _RegTree(self.max_depth, self.min_samples_leaf).fit(
                    X[idx], residual[idx])
            else:
                tree = _RegTree(self.max_depth, self.min_samples_leaf).fit(X, residual)
            F += self.learning_rate * tree.predict(X)
            self.trees.append(tree)
            self.train_score_.append(float(np.mean((y - F) ** 2)))

            if F_val is not None:
                F_val += self.learning_rate * tree.predict(X_val)
                val_mse = float(np.mean((y_val - F_val) ** 2))
                self.val_score_.append(val_mse)
                if val_mse < best_val - 1e-12:
                    best_val = val_mse
                    best_iter = m + 1
                    since_improved = 0
                else:
                    since_improved += 1
                if early_stopping_rounds is not None and since_improved >= early_stopping_rounds:
                    break

        if F_val is not None and early_stopping_rounds is not None:
            # 回滚到验证最优的那一轮
            self.best_iteration_ = best_iter
            self.trees = self.trees[:best_iter]
            self.train_score_ = self.train_score_[:best_iter]
            self.val_score_ = self.val_score_[:best_iter]

        imp = np.mean([t.feature_importances_ for t in self.trees], axis=0)
        self.feature_importances_ = imp / imp.sum() if imp.sum() > 0 else imp
        return self

    def _raw_predict(self, X: np.ndarray, n_trees: int | None = None) -> np.ndarray:
        if not self.trees:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.trees[0]._n_features:
            raise ValueError("X 特征数与训练集不一致")
        trees = self.trees if n_trees is None else self.trees[:n_trees]
        out = np.full(len(X), self.baseline_)
        for tree in trees:
            out += self.learning_rate * tree.predict(X)
        return out

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._raw_predict(X)

    def staged_predict(self, X: np.ndarray):
        """逐轮预测：第 0 个是基线，之后每加一棵树 yield 一次。"""
        X = np.asarray(X, dtype=float)
        if not np.isfinite(X).all():
            raise ValueError("X 含 NaN 或 inf")
        out = np.full(len(X), self.baseline_)
        yield out.copy()
        for tree in self.trees:
            out += self.learning_rate * tree.predict(X)
            yield out.copy()


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")


# ---------------------------------------------------------------- 分类扩展

class _Stump:
    """一维决策树桩：在加权样本上找最小分类误差的阈值。"""

    def __init__(self) -> None:
        self.feature = 0
        self.threshold = 0.0
        self.polarity = 1
        self.error_ = 0.5

    def fit(self, X, y, w):
        n, p = X.shape
        best_err, best = 1.0, None
        for f in range(p):
            order = np.argsort(X[:, f], kind="mergesort")
            xs, ys, ws = X[order, f], y[order], w[order]
            wp = np.where(ys > 0, ws, 0.0)
            wn = np.where(ys < 0, ws, 0.0)
            cwp, cwn = np.cumsum(wp), np.cumsum(wn)
            total_p, total_n = cwp[-1], cwn[-1]
            for i in range(n - 1):
                if xs[i] == xs[i + 1]:
                    continue
                lp, ln = cwp[i], cwn[i]
                rp, rn = total_p - lp, total_n - ln
                err_pos = ln + rp          # 左 +1 / 右 -1
                err_neg = lp + rn          # 左 -1 / 右 +1
                if err_pos <= err_neg:
                    err, pol = err_pos, 1
                else:
                    err, pol = err_neg, -1
                if err < best_err - 1e-15:
                    best_err = err
                    best = (f, float((xs[i] + xs[i + 1]) / 2), pol)
        if best is None:
            # 没有可用切分：预测多数类
            best = (0, float("inf"), 1 if y.mean() >= 0 else -1)
            pred = np.full(n, best[2])
            best_err = float(np.sum(w[pred != y]))
        self.feature, self.threshold, self.polarity = best
        self.error_ = best_err
        return self

    def predict(self, X):
        left = X[:, self.feature] <= self.threshold
        out = np.where(left, self.polarity, -self.polarity)
        return out


class AdaBoostClassifier:
    """AdaBoost（SAMME 二分类简化）：样本重加权 + 树桩投票。"""

    def __init__(self, n_estimators: int = 50, learning_rate: float = 1.0,
                 random_state: int | None = None) -> None:
        if n_estimators < 1:
            raise ValueError("n_estimators 至少为 1")
        if learning_rate <= 0:
            raise ValueError("learning_rate 必须为正")
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.random_state = random_state
        self.estimators_: list[_Stump] = []
        self.estimator_weights_: list[float] = []
        self.estimator_errors_: list[float] = []
        self.classes_: np.ndarray | None = None

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 2 or y.ndim != 1 or len(X) != len(y) or len(X) == 0:
            raise ValueError("X / y 形状不匹配")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        self.classes_ = np.unique(y)
        if len(self.classes_) != 2:
            raise ValueError("AdaBoostClassifier 只支持二分类")
        y_pm = np.where(y == self.classes_[0], -1.0, 1.0)
        w = np.full(len(y), 1.0 / len(y))
        self.estimators_, self.estimator_weights_, self.estimator_errors_ = [], [], []
        for _ in range(self.n_estimators):
            stump = _Stump().fit(X, y_pm, w)
            err = min(max(stump.error_, 1e-12), 1 - 1e-12)
            alpha = 0.5 * np.log((1 - err) / err) * self.learning_rate
            pred = stump.predict(X)
            w = w * np.exp(-alpha * y_pm * pred)
            w /= w.sum()
            self.estimators_.append(stump)
            self.estimator_weights_.append(float(alpha))
            self.estimator_errors_.append(float(err))
            if err >= 0.5:
                break
        return self

    def decision_function(self, X):
        if not self.estimators_:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        out = np.zeros(len(X))
        for a, s in zip(self.estimator_weights_, self.estimators_):
            out += a * s.predict(X)
        return out

    def predict_proba(self, X):
        p = 1.0 / (1.0 + np.exp(-2 * self.decision_function(X)))
        return np.column_stack([1 - p, p])

    def predict(self, X):
        d = self.decision_function(X)
        return np.where(d >= 0, self.classes_[1], self.classes_[0])

    def staged_predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.zeros(len(X))
        for a, s in zip(self.estimator_weights_, self.estimators_):
            out += a * s.predict(X)
            yield np.where(out >= 0, self.classes_[1], self.classes_[0])


class GradientBoostingClassifier:
    """二分类 GBDT：log loss 的梯度提升（回归树拟合负梯度）。"""

    def __init__(self, n_estimators: int = 100, learning_rate: float = 0.1,
                 max_depth: int = 3, min_samples_leaf: int = 1,
                 subsample: float = 1.0, random_state: int | None = None) -> None:
        if n_estimators < 1 or max_depth < 1 or min_samples_leaf < 1:
            raise ValueError("树参数必须 >=1")
        if learning_rate <= 0:
            raise ValueError("learning_rate 必须为正")
        if not (0 < subsample <= 1):
            raise ValueError("subsample 必须在 (0,1]")
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.subsample = subsample
        self.random_state = random_state
        self.trees: list[_RegTree] = []
        self.baseline_ = 0.0
        self.classes_: np.ndarray | None = None
        self.train_score_: list[float] = []
        self.feature_importances_: np.ndarray | None = None

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 2 or y.ndim != 1 or len(X) != len(y) or len(X) == 0:
            raise ValueError("X / y 形状不匹配")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        self.classes_ = np.unique(y)
        if len(self.classes_) != 2:
            raise ValueError("GradientBoostingClassifier 只支持二分类")
        yb = (y == self.classes_[1]).astype(float)
        p0 = np.clip(yb.mean(), 1e-6, 1 - 1e-6)
        self.baseline_ = float(np.log(p0 / (1 - p0)))
        F = np.full(len(y), self.baseline_)
        self.trees, self.train_score_ = [], []
        rng = np.random.default_rng(self.random_state)
        for _ in range(self.n_estimators):
            p = 1.0 / (1.0 + np.exp(-F))
            residual = yb - p
            if self.subsample < 1:
                idx = rng.choice(len(y), max(1, int(len(y) * self.subsample)), replace=False)
                tree = _RegTree(self.max_depth, self.min_samples_leaf).fit(X[idx], residual[idx])
            else:
                tree = _RegTree(self.max_depth, self.min_samples_leaf).fit(X, residual)
            F += self.learning_rate * tree.predict(X)
            self.trees.append(tree)
            p = 1.0 / (1.0 + np.exp(-F))
            self.train_score_.append(float(-np.mean(yb * np.log(np.clip(p, 1e-12, 1))
                                                   + (1 - yb) * np.log(np.clip(1 - p, 1e-12, 1)))))
        imp = np.mean([t.feature_importances_ for t in self.trees], axis=0)
        self.feature_importances_ = imp / imp.sum() if imp.sum() > 0 else imp
        return self

    def decision_function(self, X):
        if not self.trees:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.trees[0]._n_features:
            raise ValueError("X 特征数与训练集不一致")
        out = np.full(len(X), self.baseline_)
        for t in self.trees:
            out += self.learning_rate * t.predict(X)
        return out

    def predict_proba(self, X):
        p = 1.0 / (1.0 + np.exp(-self.decision_function(X)))
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return np.where(self.decision_function(X) >= 0, self.classes_[1], self.classes_[0])
