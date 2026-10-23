"""关联规则 Apriori — demo：频繁项集、规则、暴力基线

    uv run python demo.py
"""

from __future__ import annotations

import time

import numpy as np
from impl import Apriori, brute_force

ITEMS = ["bread", "milk", "eggs", "butter", "cheese", "apple", "banana",
         "coffee", "tea", "sugar", "chicken", "rice"]
PLANTED = [("bread", "milk"), ("coffee", "sugar"), ("chicken", "rice")]


def make_transactions(n=300, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        t = set(rng.choice(ITEMS, size=rng.integers(2, 6), replace=False).tolist())
        for a, b in PLANTED:
            if rng.random() < 0.8:
                t.update([a, b])
        out.append(t)
    return out


def main() -> None:
    trans = make_transactions()
    print(f"事务 {len(trans)}，商品 {len(ITEMS)}，植入规则 {PLANTED}")

    t0 = time.perf_counter()
    ap = Apriori(min_support=0.05, max_len=3).fit(trans)
    t_fit = time.perf_counter() - t0
    rules = ap.rules(min_confidence=0.5)
    print(f"频繁项集 {len(ap.frequent_itemsets_)}，规则 {len(rules)}，Apriori {t_fit * 1000:.1f}ms")

    print("\n== Top 5 规则（按 lift/confidence） ==")
    for r in rules[:5]:
        print(f"{sorted(r.antecedent)} → {sorted(r.consequent)}  "
              f"sup={r.support:.3f} conf={r.confidence:.3f} lift={r.lift:.2f}")

    # 暴力基线只在小样本上跑
    small = trans[:60]
    t0 = time.perf_counter()
    bf = brute_force(small, min_support=0.05, max_len=3)
    t_bf = time.perf_counter() - t0
    ap_small = Apriori(min_support=0.05, max_len=3).fit(small)
    print(f"\n小样本 60：Apriori {len(ap_small.frequent_itemsets_)} 项集 / "
          f"暴力 {len(bf)} 项集；一致 {set(ap_small.frequent_itemsets_) == set(bf)}；"
          f"暴力 {t_bf * 1000:.1f}ms")

    print(f"\n规则示例：{rules[0].as_dict() if rules else '无'}")
    assert set(ap_small.frequent_itemsets_) == set(bf)


if __name__ == "__main__":
    main()
