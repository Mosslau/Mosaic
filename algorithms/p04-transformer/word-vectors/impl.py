"""词向量：skip-gram + 负采样（SGNS）— 手写实现（无监督估计器 · 词嵌入）

本目录没有独立的标签 y：skip-gram 用「中心词 → 窗口内上下文词」的同现关系自造训练对，
所以入口是 `SkipGramNS.fit(sentences)`（吃分词后的句子列表），没有 `fit(X, y)`；
产出 `vectors`（词 × 维度，W_in+W_out 后已 L2 归一化）与 `most_similar` / `analogy` 两个检索接口。
词表、子采样、动态窗口、负采样表与批量 SGD 全部在本文件手写，只用 numpy。
"""

from __future__ import annotations

from collections import Counter

import numpy as np


def build_vocab(sentences, min_count=1):
    """按词频降序（同频按字典序）建词表，返回 (vocab, word2id, counts)。"""
    counts = Counter(w for s in sentences for w in s)
    vocab = [w for w, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
             if c >= min_count]
    if len(vocab) < 2:
        raise ValueError("词表不足 2 个词：检查 min_count 或语料")
    word2id = {w: i for i, w in enumerate(vocab)}
    return vocab, word2id, np.array([counts[w] for w in vocab], dtype=float)


def noise_cdf(counts, power=0.75):
    """负采样分布 ∝ 词频^0.75：压低高频词、抬高低频词，返回累积分布。"""
    p = np.asarray(counts, dtype=float) ** power
    return np.cumsum(p / p.sum())


def subsample_keep(counts, total, t):
    """word2vec 子采样保留概率 p=(sqrt(t/f)+1)·(t/f)，截断到 [0,1]。

    t 是阈值：词频 f 远高于 t 的词被大量丢弃，降低「the/and」这类词的支配。
    """
    f = np.asarray(counts, dtype=float) / total
    return np.clip((np.sqrt(t / f) + 1.0) * (t / f), 0.0, 1.0)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def l2_normalize(X):
    """按行做 L2 归一化，零向量保持为零（避免除零）。"""
    norm = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.where(norm == 0, 1.0, norm)


class SkipGramNS:
    """skip-gram with negative sampling。词向量 = 输入矩阵 W_in 的行。"""

    def __init__(self, dim=32, window=3, negative=5, lr=2.0, epochs=40, min_count=1,
                 subsample=1e-2, noise_power=0.75, batch=512, seed=0):
        if dim < 1:
            raise ValueError("dim 必须 >= 1")
        if window < 1:
            raise ValueError("window 必须 >= 1")
        if negative < 0:
            raise ValueError("negative 必须 >= 0")
        if lr <= 0 or epochs < 1 or min_count < 1 or batch < 1:
            raise ValueError("lr/epochs/min_count/batch 必须为正")
        if not 0.0 <= subsample <= 1.0:
            raise ValueError("subsample 是概率阈值，须在 [0,1]")
        if noise_power < 0:
            raise ValueError("noise_power 必须 >= 0（0 = 均匀负采样）")
        self.dim, self.window, self.negative = dim, window, negative
        self.lr, self.epochs, self.min_count = lr, epochs, min_count
        self.subsample, self.batch, self.seed = subsample, batch, seed
        self.noise_power = noise_power

    # ---------- 训练 ----------

    def fit(self, sentences):
        sents = [s.split() if isinstance(s, str) else list(s) for s in sentences]
        if not sents or not any(sents):
            raise ValueError("语料为空")
        self.vocab, self.word2id, self.counts = build_vocab(sents, self.min_count)
        V = len(self.vocab)
        # 丢掉低于 min_count 的 OOV token；句子被截短但仍保留边界
        ids = [[self.word2id[w] for w in s if w in self.word2id] for s in sents]
        ids = [np.asarray(a, dtype=np.int64) for a in ids if a]
        if not ids:
            raise ValueError("min_count 过滤后语料为空")
        flat = np.concatenate(ids)
        sent_id = np.repeat(np.arange(len(ids)), [len(a) for a in ids])
        self.n_tokens = int(len(flat))
        self.n_sentences = len(ids)

        rng = np.random.default_rng(self.seed)
        cdf = noise_cdf(self.counts, self.noise_power)
        keep = subsample_keep(self.counts, float(self.counts.sum()), self.subsample)
        self.W_in = rng.normal(0.0, 0.1, (V, self.dim))
        self.W_out = np.zeros((V, self.dim))
        self.loss_history = []
        self.n_pairs = 0
        for _ in range(self.epochs):
            centers, contexts = self._sample_pairs(flat, sent_id, keep, rng)
            self.n_pairs += int(len(centers))
            self.loss_history.append(self._train_epoch(centers, contexts, cdf, rng))
        # 输入/输出矩阵各学到词的一个侧面：类比用两者之和更稳（见 README「实现要点」）
        self.vectors = l2_normalize(self.W_in + self.W_out)
        return self

    def train(self, sentences):
        """`fit` 的别名：本族其它实验（BERT/GPT）用 `train(data)`，保持调用一致。"""
        return self.fit(sentences)

    def _sample_pairs(self, flat, sent_id, keep, rng):
        """按句子边界切窗口；窗口宽度每个位置独立收缩；再按 keep 概率子采样。"""
        n = len(flat)
        widths = rng.integers(1, self.window + 1, n)      # 距离 d 只在 d<=width 时成对
        kept = rng.random(n) < keep[flat]
        cs, os_ = [], []
        for d in range(1, self.window + 1):
            same = sent_id[:-d] == sent_id[d:]
            ok = same & kept[:-d] & kept[d:]
            left = np.flatnonzero(ok & (widths[:-d] >= d))       # 中心在左、上下文在右
            right = np.flatnonzero(ok & (widths[d:] >= d))       # 中心在右、上下文在左
            cs.append(np.concatenate([left, right + d]))
            os_.append(np.concatenate([left + d, right]))
        if not cs or sum(len(a) for a in cs) == 0:
            return np.empty(0, np.int64), np.empty(0, np.int64)
        return flat[np.concatenate(cs)], flat[np.concatenate(os_)]

    def _train_epoch(self, centers, contexts, cdf, rng):
        """同步小批量 SGD：一个 batch 内所有梯度基于同一份参数快照累加后再更新。"""
        n = len(centers)
        if n == 0:
            return 0.0
        perm = rng.permutation(n)
        centers, contexts = centers[perm], contexts[perm]
        total = 0.0
        scale = self.lr / self.batch
        for start in range(0, n, self.batch):
            c = centers[start:start + self.batch]
            o = contexts[start:start + self.batch]
            B = len(c)
            neg = np.searchsorted(cdf, rng.random((B, self.negative)), side="right")
            neg = np.minimum(neg, len(cdf) - 1)                 # searchsorted 右端越界保护
            vc = self.W_in[c]                                    # (B,d)
            uo = self.W_out[o]                                   # (B,d)
            un = self.W_out[neg]                                 # (B,k,d)
            pos = np.einsum("bd,bd->b", vc, uo)
            neg_dot = np.einsum("bd,bkd->bk", vc, un)
            total += float(-np.log(sigmoid(pos) + 1e-12).sum()
                           - np.log(sigmoid(-neg_dot) + 1e-12).sum())
            dpos = sigmoid(pos) - 1.0                            # ∂L/∂(vc·uo)
            dneg = sigmoid(neg_dot)                              # ∂L/∂(vc·un)
            grad_v = dpos[:, None] * uo + np.einsum("bk,bkd->bd", dneg, un)
            idx_out = np.concatenate([o, neg.ravel()])
            grad_out = np.concatenate([(dpos[:, None] * vc).reshape(-1, self.dim),
                                       (dneg[:, :, None] * vc[:, None, :]).reshape(-1, self.dim)])
            np.add.at(self.W_in, c, -scale * grad_v)             # 同词多次出现会正确累加
            np.add.at(self.W_out, idx_out, -scale * grad_out)
        return total / n

    # ---------- 查询 ----------

    def __getitem__(self, word):
        return self.vectors[self.word2id[word]]

    def _id(self, word):
        if word not in self.word2id:
            raise KeyError(f"词 {word!r} 不在词表中（min_count={self.min_count} 过滤或未出现）")
        return self.word2id[word]

    def most_similar(self, word, topk=5):
        i = self._id(word)
        sims = self.vectors @ self.vectors[i]
        sims[i] = -np.inf
        order = np.argsort(-sims)[:topk]
        return [(self.vocab[j], float(sims[j])) for j in order]

    def analogy(self, a, b, c, topk=1):
        """解 a:b :: c:? —— 目标向量 = v(b) - v(a) + v(c)，按余弦排序并排除查询词。"""
        target = self.vectors[self._id(b)] - self.vectors[self._id(a)] + self.vectors[self._id(c)]
        norm = np.linalg.norm(target)
        if norm > 0:
            target = target / norm
        sims = self.vectors @ target
        for w in (a, b, c):
            sims[self._id(w)] = -np.inf
        order = np.argsort(-sims)[:topk]
        return [(self.vocab[j], float(sims[j])) for j in order]

    def similarity(self, w1, w2):
        return float(self.vectors[self._id(w1)] @ self.vectors[self._id(w2)])


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：.venv/bin/python demo.py")
