"""迷你 RAG — demo：检索命中、答案/引用、BM25 对照

    uv run python demo.py
"""

from __future__ import annotations

import time

import framework
import numpy as np
from impl import Generator, Index, Pipeline

DOCS = [
    "A star search orders nodes by f = g + h. h must be admissible for optimality.",
    "MCTS uses UCB1 to balance exploration and exploitation, with random rollouts.",
    "Minimax with alpha beta pruning cuts branches when alpha >= beta.",
    "CSP backtracking uses MRV: choose the variable with fewest legal values.",
    "K means assigns points to the nearest center, then updates each center to the mean.",
    "PCA projects data onto directions that maximize variance, using eigenvectors.",
    "Logistic regression minimizes binary cross entropy and outputs a probability.",
    "SVM with an RBF kernel maps data to a higher dimensional space for a nonlinear boundary.",
    "A decision tree splits on the feature that maximizes information gain or lowers entropy.",
    "Random forest uses bootstrap samples and OOB samples for validation.",
    "GAN training is a minimax game between a generator and a discriminator.",
    "DDPM adds Gaussian noise forward and learns to denoise step by step for sampling.",
]

QUERIES = [
    ("What function does A star use to order nodes?", 0, "f = g + h"),
    ("Which rule does MCTS use for selection?", 1, "UCB1"),
    ("When does alpha beta pruning cut a branch?", 2, "alpha >= beta"),
    ("Which variable ordering does CSP backtracking use?", 3, "MRV"),
    ("How are K means centers updated?", 4, "mean"),
    ("What does PCA maximize?", 5, "variance"),
    ("What loss does logistic regression minimize?", 6, "cross entropy"),
    ("Which kernel does SVM use for nonlinear boundaries?", 7, "RBF"),
    ("What impurity does a decision tree reduce?", 8, "entropy"),
    ("What samples does random forest use for validation?", 9, "OOB"),
    ("What kind of game is GAN training?", 10, "minimax"),
    ("How does DDPM generate samples?", 11, "denoise"),
]


def retrieval_metrics(hits_by_q, k=3):
    recall, mrr = [], []
    for hits, (_, gold, _) in zip(hits_by_q, QUERIES):
        ids = [h.doc_id for h in hits[:k]]
        recall.append(1.0 if gold in ids else 0.0)
        rank = next((i + 1 for i, d in enumerate(ids) if d == gold), None)
        mrr.append(1.0 / rank if rank else 0.0)
    return float(np.mean(recall)), float(np.mean(mrr))


def main() -> None:
    idx = Index(chunk_size=200, overlap=40).build(DOCS)
    pipe = Pipeline(idx, Generator())
    print(f"文档 {len(DOCS)}，chunk {len(idx.chunks)}，词表哈希维度 {idx.vectors.shape[1]}")

    k = 3
    t0 = time.perf_counter()
    hits = [idx.search(q, k) for q, _, _ in QUERIES]
    t_hand = time.perf_counter() - t0
    recall, mrr = retrieval_metrics(hits, k)
    print("\n== 检索（手写 TF-IDF 哈希） ==")
    print(f"Recall@{k} {recall:.3f}；MRR {mrr:.3f}；{t_hand * 1000:.1f}ms")

    t0 = time.perf_counter()
    base = framework.run_retrieval_baseline(idx, [q for q, _, _ in QUERIES], k)
    t_base = time.perf_counter() - t0
    brecall, bmrr = retrieval_metrics(base, k)
    print(f"BM25/TF-IDF 基线：Recall@{k} {brecall:.3f}；MRR {bmrr:.3f}；"
          f"{t_base * 1000:.1f}ms")

    print("\n== 端到端（抽取式降级，无 LLM） ==")
    match, cite, lat = [], [], []
    for q, gold_doc, gold_ans in QUERIES:
        t0 = time.perf_counter()
        a = pipe.query(q, k)
        lat.append(time.perf_counter() - t0)
        match.append(1.0 if gold_ans.lower() in a.text.lower() else 0.0)
        cite.append(1.0 if gold_doc in [c.doc_id for c in a.citations] else 0.0)
    print(f"answer match {np.mean(match):.3f}；citation hit {np.mean(cite):.3f}；"
          f"平均 {np.mean(lat) * 1000:.2f}ms")

    print("\n== 一个例子 ==")
    q, gold_doc, _ = QUERIES[0]
    a = pipe.query(q, k)
    print(f"Q: {q}")
    print(f"A: {a.text}")
    print(f"citations: {[c.doc_id for c in a.citations]}")


if __name__ == "__main__":
    main()
