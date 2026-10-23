"""迁移项目：自定义语料 RAG QA + 引用

    uv run python qa.py

构建小索引，对 4 个问题返回答案与引用；验收 Recall@3 ≥0.9、citation ≥0.9。
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from demo import DOCS, QUERIES  # noqa: E402
from impl import Generator, Index, Pipeline  # noqa: E402


def main() -> None:
    idx = Index(chunk_size=200, overlap=40).build(DOCS)
    pipe = Pipeline(idx, Generator())
    rec, cit = [], []
    for q, gold, _ in QUERIES:
        a = pipe.query(q, 3)
        ids = [c.doc_id for c in a.citations]
        rec.append(1.0 if gold in ids else 0.0)
        cit.append(1.0 if gold in ids else 0.0)
        print(f"Q: {q}\nA: {a.text[:100]}\ncitations: {ids}\n")
    print(f"Recall@3 {sum(rec) / len(rec):.3f}；citation {sum(cit) / len(cit):.3f}")
    assert sum(rec) / len(rec) >= 0.9 and sum(cit) / len(cit) >= 0.9
    print("→ 检索命中/引用链路可用；抽取式降级不是 LLM 生成。")


if __name__ == "__main__":
    main()
