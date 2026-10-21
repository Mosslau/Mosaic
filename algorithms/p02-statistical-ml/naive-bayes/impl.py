"""朴素贝叶斯 — 手写实现（监督估计器）

本族的异类：**没有训练循环、没有梯度**，fit 只是数频次（参数估计）。
要手写的是概率本身——先验、条件概率、以及对"条件独立假设"的取舍。

    nb = MultinomialNB(alpha=1.0)       # alpha 是拉普拉斯平滑系数
    nb.fit(X_train, y_train)             # X 是词频/计数矩阵
    label = nb.predict(X_test)
    proba = nb.predict_proba(X_test)

    gnb = GaussianNB()                   # 连续特征
    vec = CountVectorizer()              # 手写词袋：文本 → 计数矩阵
"""

from __future__ import annotations

import re

import numpy as np


def _logsumexp(a: np.ndarray) -> np.ndarray:
    """沿最后一维做 logsumexp，避免连乘下溢。"""
    m = np.max(a, axis=1, keepdims=True)
    m = np.where(np.isfinite(m), m, 0.0)
    with np.errstate(divide="ignore"):
        return (m + np.log(np.sum(np.exp(a - m), axis=1, keepdims=True))).ravel()


def _check_counts(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if X.ndim != 2:
        raise ValueError(f"X 必须是二维，实际 {X.shape}")
    if np.any(X < 0):
        raise ValueError("计数矩阵不能有负数")
    if not np.all(np.isfinite(X)):
        raise ValueError("X 含 NaN 或 inf")
    return X


class CountVectorizer:
    """极简词袋：小写化、按 `\\w+` 切词、统计词频。"""

    def __init__(self, min_df: int = 1, binary: bool = False) -> None:
        if min_df < 1:
            raise ValueError("min_df 至少为 1")
        self.min_df = int(min_df)
        self.binary = bool(binary)
        self.vocabulary_: dict[str, int] = {}

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower(), flags=re.UNICODE)

    def fit(self, docs) -> CountVectorizer:
        counts: dict[str, int] = {}
        for doc in docs:
            for tok in set(self._tokens(doc)):
                counts[tok] = counts.get(tok, 0) + 1
        vocab = sorted(t for t, c in counts.items() if c >= self.min_df)
        self.vocabulary_ = {t: i for i, t in enumerate(vocab)}
        return self

    def transform(self, docs) -> np.ndarray:
        if not self.vocabulary_:
            raise RuntimeError("词表为空：先 fit")
        X = np.zeros((len(docs), len(self.vocabulary_)), dtype=float)
        for i, doc in enumerate(docs):
            for tok in self._tokens(doc):
                j = self.vocabulary_.get(tok)
                if j is not None:
                    X[i, j] = 1.0 if self.binary else X[i, j] + 1.0
        return X

    def fit_transform(self, docs) -> np.ndarray:
        return self.fit(docs).transform(docs)


class MultinomialNB:
    """多项式朴素贝叶斯：P(c)、P(w|c)，拉普拉斯平滑 + 对数域。"""

    def __init__(self, alpha: float = 1.0) -> None:
        if alpha < 0:
            raise ValueError("alpha 不能为负")
        self.alpha = float(alpha)
        self.classes_: np.ndarray | None = None
        self.class_count_: np.ndarray | None = None
        self.feature_count_: np.ndarray | None = None
        self.class_log_prior_: np.ndarray | None = None
        self.feature_log_prob_: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> MultinomialNB:
        X = _check_counts(X)
        y = np.asarray(y)
        if len(X) != len(y):
            raise ValueError("X / y 长度不一致")
        if len(X) == 0:
            raise ValueError("样本数为 0")
        self.classes_, y_idx = np.unique(y, return_inverse=True)
        k, d = len(self.classes_), X.shape[1]
        counts = np.zeros((k, d))
        for c in range(k):
            counts[c] = X[y_idx == c].sum(axis=0)
        # 先验用"文档数/类"，不是"总词数/类"；后者会把长文档的类先验抬高
        self.class_count_ = np.bincount(y_idx, minlength=k).astype(float)
        self.feature_count_ = counts
        self.class_log_prior_ = np.log(self.class_count_ / len(X))
        smoothed = counts + self.alpha
        denom = smoothed.sum(axis=1, keepdims=True) + 1e-300
        with np.errstate(divide="ignore"):
            self.feature_log_prob_ = np.log(smoothed / denom)
        return self

    def _joint_log_likelihood(self, X: np.ndarray) -> np.ndarray:
        X = _check_counts(X)
        if X.shape[1] != self.feature_log_prob_.shape[1]:
            raise ValueError("特征数与训练集不一致")
        return X @ self.feature_log_prob_.T + self.class_log_prior_

    def predict_log_proba(self, X: np.ndarray) -> np.ndarray:
        jll = self._joint_log_likelihood(X)
        lse = _logsumexp(jll)
        bad = ~np.isfinite(lse)
        if np.any(bad):
            # alpha=0 且测试样本含"两类都没见过"的词：所有后验为 0，
            # 回退成均匀分布，避免 nan。
            jll = jll.copy()
            jll[bad] = 0.0
            lse[bad] = np.log(len(self.classes_))
        return jll - lse[:, None]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.exp(self.predict_log_proba(X))

    def predict(self, X: np.ndarray) -> np.ndarray:
        jll = self._joint_log_likelihood(X)
        return self.classes_[np.argmax(jll, axis=1)]


class GaussianNB:
    """高斯朴素贝叶斯：每个类、每个特征独立高斯。"""

    def __init__(self, var_smoothing: float = 1e-9) -> None:
        if var_smoothing < 0:
            raise ValueError("var_smoothing 不能为负")
        self.var_smoothing = float(var_smoothing)
        self.classes_: np.ndarray | None = None
        self.theta_: np.ndarray | None = None
        self.var_: np.ndarray | None = None
        self.class_prior_: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> GaussianNB:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 2 or len(X) != len(y):
            raise ValueError("X / y 形状不匹配")
        if not np.all(np.isfinite(X)):
            raise ValueError("X 含 NaN 或 inf")
        self.classes_, y_idx = np.unique(y, return_inverse=True)
        k, d = len(self.classes_), X.shape[1]
        self.theta_ = np.zeros((k, d))
        self.var_ = np.zeros((k, d))
        for c in range(k):
            Xc = X[y_idx == c]
            self.theta_[c] = Xc.mean(axis=0)
            self.var_[c] = Xc.var(axis=0)
        eps = self.var_smoothing * float(np.max(self.var_)) if np.max(self.var_) > 0 else 1e-9
        self.var_ = self.var_ + eps
        self.class_prior_ = np.bincount(y_idx) / len(X)
        return self

    def _joint_log_likelihood(self, X: np.ndarray) -> np.ndarray:
        if self.theta_ is None:
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.theta_.shape[1]:
            raise ValueError("特征数与训练集不一致")
        jll = np.zeros((len(X), len(self.classes_)))
        for c in range(len(self.classes_)):
            var = self.var_[c]
            jll[:, c] = (np.log(self.class_prior_[c])
                         - 0.5 * np.sum(np.log(2 * np.pi * var))
                         - 0.5 * np.sum((X - self.theta_[c]) ** 2 / var, axis=1))
        return jll

    def predict_log_proba(self, X: np.ndarray) -> np.ndarray:
        jll = self._joint_log_likelihood(X)
        return jll - _logsumexp(jll)[:, None]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.exp(self.predict_log_proba(X))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.classes_[np.argmax(self._joint_log_likelihood(X), axis=1)]


# 骨架里用的名字；默认对应多项式版本
NaiveBayes = MultinomialNB


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
