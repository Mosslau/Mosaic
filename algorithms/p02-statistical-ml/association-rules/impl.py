"""关联规则 Apriori — 手写实现（无监督 · 频繁项集）

    ap = Apriori(min_support=0.05, max_len=3).fit(transactions)
    ap.frequent_itemsets_          # {frozenset: support}
    rules = ap.rules(min_confidence=0.6)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Rule:
    antecedent: frozenset
    consequent: frozenset
    support: float
    confidence: float
    lift: float

    def as_dict(self) -> dict:
        return {"antecedent": sorted(self.antecedent), "consequent": sorted(self.consequent),
                "support": round(self.support, 4),
                "confidence": round(self.confidence, 4), "lift": round(self.lift, 4)}


class Apriori:
    def __init__(self, min_support: float = 0.05, max_len: int | None = 3) -> None:
        if not (0 < min_support <= 1):
            raise ValueError("min_support 必须在 (0,1]")
        if max_len is not None and max_len < 1:
            raise ValueError("max_len 必须 >=1 或 None")
        self.min_support = float(min_support)
        self.max_len = max_len
        self.n_transactions_ = 0
        self.frequent_itemsets_: dict[frozenset, float] = {}
        self.support_count_: dict[frozenset, int] = {}

    def _count(self, transactions, itemset):
        return sum(1 for t in transactions if itemset.issubset(t))

    def fit(self, transactions: list[set]) -> Apriori:
        if not transactions:
            raise ValueError("transactions 不能为空")
        trans = [set(t) for t in transactions]
        self.n_transactions_ = len(trans)
        min_count = max(1, int(np.ceil(self.min_support * len(trans))))
        self.frequent_itemsets_, self.support_count_ = {}, {}

        counts = {}
        for t in trans:
            for item in t:
                key = frozenset([item])
                counts[key] = counts.get(key, 0) + 1
        current = {k: v for k, v in counts.items() if v >= min_count}
        k = 1
        while current:
            for itemset, c in current.items():
                self.frequent_itemsets_[itemset] = c / len(trans)
                self.support_count_[itemset] = c
            if self.max_len is not None and k >= self.max_len:
                break
            items = sorted(current)
            candidates = set()
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    u = a | b
                    if len(u) == k + 1:
                        candidates.add(u)
            nxt = {}
            for c in candidates:
                if all(frozenset(s) in current for s in _subsets(c, k)):
                    cnt = self._count(trans, c)
                    if cnt >= min_count:
                        nxt[c] = cnt
            current = nxt
            k += 1
        return self

    def rules(self, min_confidence: float = 0.5) -> list[Rule]:
        if not (0 < min_confidence <= 1):
            raise ValueError("min_confidence 必须在 (0,1]")
        out = []
        for itemset, sup in self.frequent_itemsets_.items():
            if len(itemset) < 2:
                continue
            for r in range(1, len(itemset)):
                for ant in _subsets(itemset, r):
                    ant = frozenset(ant)
                    con = itemset - ant
                    conf = sup / self.frequent_itemsets_[ant]
                    if conf >= min_confidence:
                        lift = conf / self.frequent_itemsets_[con]
                        out.append(Rule(ant, con, sup, conf, lift))
        return sorted(out, key=lambda x: (x.lift, x.confidence), reverse=True)


def _subsets(itemset, k):
    """生成 itemset 的所有 k 元子集（itertools 手写版，保持确定性）。"""
    items = sorted(itemset)
    out = []

    def rec(start, cur):
        if len(cur) == k:
            out.append(tuple(cur))
            return
        for i in range(start, len(items)):
            rec(i + 1, cur + [items[i]])

    rec(0, [])
    return out


def brute_force(transactions, min_support=0.05, max_len=3):
    """小数据基线：枚举所有子集，返回 frequent_itemsets。"""
    items = sorted({x for t in transactions for x in t})
    n = len(transactions)
    min_count = max(1, int(np.ceil(min_support * n)))
    out = {}
    for r in range(1, min(max_len or len(items), len(items)) + 1):
        for combo in _subsets(items, r):
            s = frozenset(combo)
            c = sum(1 for t in transactions if s.issubset(t))
            if c >= min_count:
                out[s] = c / n
    return out


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
