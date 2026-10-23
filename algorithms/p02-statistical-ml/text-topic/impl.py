"""文本主题模型 — 手写 TF-IDF + NMF"""

from __future__ import annotations

import re
from collections import Counter

import numpy as np

STOP = set(
    "a an the and or of to in on for with is are was were be by as at from "
    "that this it its".split()
)


def tokenize(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP]


class Tfidf:
    def fit(self, docs):
        self.vocab = sorted({w for d in docs for w in tokenize(d)})
        self.stoi = {w: i for i, w in enumerate(self.vocab)}
        df = np.zeros(len(self.vocab))
        for d in docs:
            for w in set(tokenize(d)):
                df[self.stoi[w]] += 1
        self.idf = np.log((len(docs) + 1) / (df + 1)) + 1
        return self

    def transform(self, docs):
        X = np.zeros((len(docs), len(self.vocab)))
        for i, d in enumerate(docs):
            tf = Counter(tokenize(d))
            for w, c in tf.items():
                if w in self.stoi:
                    X[i, self.stoi[w]] = (1 + np.log(c)) * self.idf[self.stoi[w]]
        norm = np.linalg.norm(X, axis=1, keepdims=True)
        return X / np.maximum(norm, 1e-12)


class NMF:
    def __init__(self, n_topics=3, epochs=200, random_state=0):
        if n_topics < 1 or epochs < 1:
            raise ValueError("n_topics/epochs 必须 >=1")
        self.n_topics, self.epochs, self.random_state = n_topics, epochs, random_state

    def fit(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.min() < 0:
            raise ValueError("X 应为非负二维矩阵")
        rng = np.random.default_rng(self.random_state)
        n, d = X.shape
        self.W = rng.random((n, self.n_topics)) + 1e-3
        self.H = rng.random((self.n_topics, d)) + 1e-3
        self.loss_history = []
        for _ in range(self.epochs):
            # multiplicative updates，eps 防 0
            self.H *= (self.W.T @ X) / (self.W.T @ self.W @ self.H + 1e-12)
            self.W *= (X @ self.H.T) / (self.W @ self.H @ self.H.T + 1e-12)
            self.loss_history.append(float(np.linalg.norm(X - self.W @ self.H)))
        return self

    def transform(self, X):
        if not hasattr(self, "W"):
            raise RuntimeError("模型尚未训练")
        X = np.asarray(X, dtype=float)
        # 固定 H 做一次最小二乘式投影（非负乘法更新）
        W = np.random.default_rng(self.random_state).random((len(X), self.n_topics)) + 1e-3
        for _ in range(100):
            W *= (X @ self.H.T) / (W @ self.H @ self.H.T + 1e-12)
        return W

    def top_words(self, vocab, n=5):
        if not hasattr(self, "H"):
            raise RuntimeError("模型尚未训练")
        return [[vocab[j] for j in np.argsort(self.H[k])[::-1][:n]]
                for k in range(self.n_topics)]


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
