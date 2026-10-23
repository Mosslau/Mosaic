"""RAG — 检索基线（TF-IDF/BM25 口径）。

生成环节需要外部 LLM；无凭据时不伪造，只在 README 标注“未在本环境验证”。
"""

from __future__ import annotations

import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


def run_retrieval_baseline(index, queries, top_k=3):
    """用 sklearn TF-IDF + 余弦相似度做词法检索基线，返回与 Hit 对齐的对象。"""
    if top_k < 1:
        raise ValueError("top_k 必须 >=1")
    t0 = time.perf_counter()
    vec = TfidfVectorizer()
    X = vec.fit_transform(index.chunks)
    Q = vec.transform(queries)
    scores = linear_kernel(Q, X)
    out = []
    for row in scores:
        order = row.argsort()[::-1][:top_k]
        out.append([_BaselineHit(index.chunks[i], float(row[i]), index.doc_ids[i])
                    for i in order])
    out_ms = (time.perf_counter() - t0) * 1000
    print(f"（基线内部耗时 {out_ms:.1f}ms）")
    return out


class _BaselineHit:
    def __init__(self, text, score, doc_id):
        self.text, self.score, self.doc_id = text, score, doc_id


def run_pipeline_baseline(*args, **kwargs):
    raise RuntimeError("无 LLM 凭据：端到端生成基线未在本环境验证")

if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
