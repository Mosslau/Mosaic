"""迁移项目：把 SGNS 词向量封装成「关系检索」小服务，并在三个任务上验收。

与教学 demo 的差别（新约束）：
  A. 类比检索仍是 3CosAdd，但走统一的检索接口（候选池可裁剪）；
  B. 关系补全在**受限候选池**里检索（模拟知识库只收某类实体）——demo 没有这个任务；
  C. 同类别检索要求排除配对词，衡量「类别结构」而不是「配对记忆」。

运行：cd algorithms/p04-transformer/word-vectors && ../../.venv/bin/python project/search.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402

from demo import (GROUP_OF, PARTNER_OF, RELATION_SETS, analogy_items,  # noqa: E402
                  build_corpus)
from impl import SkipGramNS, l2_normalize  # noqa: E402


class RelationIndex:
    """词向量的检索层：训练一次，之后所有查询都走这里的接口。"""

    def __init__(self, dim=32, epochs=40, seed=0):
        sentences, self.meta = build_corpus(seed)
        self.model = SkipGramNS(dim=dim, epochs=epochs, seed=seed).fit(sentences)
        self.vectors = l2_normalize(self.model.vectors)
        self.vocab = self.model.vocab
        self.word2id = self.model.word2id
        self.relation_words = [w for w in self.vocab if w in GROUP_OF]

    # ---------- 检索接口 ----------

    def nearest(self, word, topk=5, candidates=None, block=()):
        """按余弦检索最近词；candidates 限定候选池，block 里的词一律不返回。"""
        pool = self.relation_words if candidates is None else list(candidates)
        pool = [w for w in pool if w in self.word2id]
        sims = self.vectors[[self.word2id[w] for w in pool]] @ self.vectors[self.word2id[word]]
        banned = set(block) | {word}
        order = [i for i in np.argsort(-sims) if pool[i] not in banned][:topk]
        return [(pool[i], float(sims[i])) for i in order]

    def analogy(self, a, b, c, topk=1):
        """a:b :: c:?，返回排除 a/b/c 后的 top-k。"""
        target = self.vectors[self.word2id[b]] - self.vectors[self.word2id[a]] \
            + self.vectors[self.word2id[c]]
        target = target / (np.linalg.norm(target) + 1e-12)
        scores = self.vectors @ target
        for w in (a, b, c):
            scores[self.word2id[w]] = -np.inf
        order = np.argsort(-scores)[:topk]
        return [(self.vocab[i], float(scores[i])) for i in order]

    def complete(self, left_word, relation):
        """在指定关系的**右词候选池**里检索左词的搭档（关系补全）。"""
        pairs = dict(RELATION_SETS)[relation]
        right = [b for _, b in pairs]
        target = self.vectors[self.word2id[left_word]]
        sims = self.vectors[[self.word2id[w] for w in right]] @ target
        return right[int(np.argmax(sims))], float(sims.max())


# ---------- 三个验收任务 ----------

def task_analogy(index, items):
    hits = 0
    for it in items:
        hits += int(index.analogy(it["a"], it["b"], it["c"], 1)[0][0] == it["d"])
    return hits / len(items)


def task_completion(index):
    per, hits, total = {}, 0, 0
    for name, pairs in RELATION_SETS:
        ok = 0
        for a, b in pairs:
            ok += int(index.complete(a, name)[0] == b)
            total += 1
        per[name] = f"{ok}/{len(pairs)}"
        hits += ok
    return hits / total, per


def task_category(index, topk=3):
    prec = []
    for w in index.relation_words:
        got = index.nearest(w, topk=topk, candidates=index.relation_words,
                            block=(PARTNER_OF[w],))
        prec.append(np.mean([GROUP_OF[t] == GROUP_OF[w] for t, _ in got]))
    return float(np.mean(prec))


def main() -> None:
    index = RelationIndex()
    held = [it for it in analogy_items() if it["split"] == "heldout"]
    acc_a = task_analogy(index, held)
    acc_b, per = task_completion(index)
    acc_c = task_category(index)

    print(f"索引：{index.meta['vocab']} 词 × 32 维（{index.meta['tokens']} token 语料）")
    print(f"A. 类比检索（{len(held)} 题留出）top-1      ：{acc_a:.3f}")
    print(f"B. 关系补全（候选池内）top-1          ：{acc_b:.3f}   {per}")
    print(f"C. 同类别检索 precision@3（排除配对词）：{acc_c:.3f}")
    print(f"检索示例：valdoria 的最近关系词 {index.nearest('valdoria', 3)}")
    print(f"类比示例：valdoria:valport :: kestry:? → "
          f"{index.analogy('valdoria', 'valport', 'kestry', 1)[0][0]}")

    assert acc_a > 0.75, "类比检索偏低"
    assert acc_b > 0.70, "关系补全偏低"
    assert acc_c > 0.85, "同类别检索偏低"
    print("\n验收通过：A/B/C 三项均达到 README 的阈值。")


if __name__ == "__main__":
    main()
