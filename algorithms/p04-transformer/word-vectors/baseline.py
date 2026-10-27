"""词向量对照基线：PPMI + 截断 SVD（Levy & Goldberg 2014 的 SGNS 隐式分解）。

与 impl.py 的 SGNS 吃同一份分词句子、用同一个窗口统计共现：
  1. 共现矩阵 C[w,c] += 1/距离（对称窗口，5.3.1 之前的经典分布式表示做法）；
  2. PPMI = max(0, log( p(w,c) / (p(w)·p_α(c)) ))，上下文分布做 α=0.75 平滑；
  3. sklearn 的 TruncatedSVD 取前 dim 个奇异向量当词向量（基线不受手写纪律约束）。
"""

from __future__ import annotations

import numpy as np
from impl import build_vocab, l2_normalize
from sklearn.decomposition import TruncatedSVD


def build_cooc(sentences, word2id, window=3):
    """对称距离加权共现：距离 d 记 1/d，双向各记一次。"""
    V = len(word2id)
    C = np.zeros((V, V), dtype=np.float64)
    for s in sentences:
        ids = [word2id[w] for w in s if w in word2id]
        for i, wi in enumerate(ids):
            for d in range(1, window + 1):
                if i + d < len(ids):
                    C[wi, ids[i + d]] += 1.0 / d
                    C[ids[i + d], wi] += 1.0 / d
    return C


def ppmi(C, alpha=0.75, eps=1e-12):
    """正点互信息：只保留正相关，否则大量 0 计数会主导 SVD。"""
    total = C.sum()
    if total <= 0:
        raise ValueError("共现矩阵为空")
    row = C.sum(1, keepdims=True)
    col = C.sum(0, keepdims=True) ** alpha          # 上下文分布平滑
    col = col / col.sum()
    pmi = np.log((C / total + eps) / (row / total * col + eps))
    return np.maximum(pmi, 0.0)


class PPMISVD:
    """PPMI + 截断 SVD 基线；接口与 impl.SkipGramNS 对齐（vectors / most_similar / analogy）。"""

    def __init__(self, dim=32, window=3, alpha=0.75, min_count=1, seed=0):
        if dim < 1 or window < 1 or min_count < 1:
            raise ValueError("dim/window/min_count 必须为正")
        self.dim, self.window, self.alpha = dim, window, alpha
        self.min_count, self.seed = min_count, seed

    def fit(self, sentences):
        sents = [s.split() if isinstance(s, str) else list(s) for s in sentences]
        if not sents or not any(sents):
            raise ValueError("语料为空")
        self.vocab, self.word2id, self.counts = build_vocab(sents, self.min_count)
        C = build_cooc(sents, self.word2id, self.window)
        self.cooc = C
        M = ppmi(C, self.alpha)
        n_comp = min(self.dim, min(M.shape) - 1)     # SVD 要求 n_components < min(shape)
        svd = TruncatedSVD(n_components=n_comp, random_state=self.seed)
        self.vectors = l2_normalize(svd.fit_transform(M))
        if n_comp < self.dim:                        # 维度不足时补零，保持接口形状一致
            pad = np.zeros((len(self.vocab), self.dim - n_comp))
            self.vectors = np.hstack([self.vectors, pad])
        self.explained = float(svd.explained_variance_ratio_.sum())
        return self

    def _id(self, word):
        if word not in self.word2id:
            raise KeyError(f"词 {word!r} 不在词表中")
        return self.word2id[word]

    def most_similar(self, word, topk=5):
        i = self._id(word)
        sims = self.vectors @ self.vectors[i]
        sims[i] = -np.inf
        return [(self.vocab[j], float(sims[j])) for j in np.argsort(-sims)[:topk]]

    def analogy(self, a, b, c, topk=1):
        target = self.vectors[self._id(b)] - self.vectors[self._id(a)] + self.vectors[self._id(c)]
        target = l2_normalize(target.reshape(1, -1))[0]
        sims = self.vectors @ target
        for w in (a, b, c):
            sims[self._id(w)] = -np.inf
        return [(self.vocab[j], float(sims[j])) for j in np.argsort(-sims)[:topk]]


if __name__ == "__main__":
    raise SystemExit("本文件是基线库，由 demo.py 调用")
