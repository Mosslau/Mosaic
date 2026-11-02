"""RAG — 性质测试（pytest）"""

import pytest
from demo import DOCS, HELDOUT_QUERIES, QUERIES
from impl import Generator, Index, Pipeline


def build():
    return Index(chunk_size=60, overlap=10).build(DOCS)


def test_build_chunks_and_vectors() -> None:
    idx = build()
    # chunk_size=60 < 文档长度：切块必须真的触发，而不是 1 doc = 1 chunk
    assert len(idx.chunks) > len(DOCS)
    assert idx.vectors.shape[0] == len(idx.chunks)
    assert idx.vectors.shape[1] == 512


def test_search_topk_and_docid() -> None:
    idx = build()
    hits = idx.search("A star heuristic f g h", 3)
    assert len(hits) == 3
    assert hits[0].doc_id == 0
    assert hits[0].score >= hits[-1].score


def test_pipeline_citations() -> None:
    idx = build()
    a = Pipeline(idx, Generator()).query("Which rule does MCTS use for selection?", 3)
    assert len(a.citations) == 1
    assert a.citations[0].doc_id == 1
    assert "UCB1" in a.text


def test_citation_is_top1_not_recall() -> None:
    """引用只取 top-1，因此它与 Recall@3 是两个不同指标。"""
    idx = build()
    q = "Which rule does MCTS use for selection?"
    a = Pipeline(idx, Generator()).query(q, 3)
    assert [c.doc_id for c in a.citations] == [idx.search(q, 3)[0].doc_id]


def test_generator_empty_contexts() -> None:
    assert "未找到" in Generator().generate("q", [])


def test_generator_fallback() -> None:
    idx = build()
    a = Pipeline(idx, Generator()).query("What does PCA maximize?", 2)
    assert "[doc" in a.text
    assert a.citations[0].doc_id == 5


def test_generator_llm_prompt() -> None:
    seen = {}

    def llm(prompt):
        seen["prompt"] = prompt
        return "ok"

    idx = build()
    a = Pipeline(idx, Generator(llm)).query("What does PCA maximize?", 2)
    assert a.text == "ok"
    assert "问题" in seen["prompt"] and "上下文" in seen["prompt"]


def test_recall_on_fixture() -> None:
    idx = build()
    hit = 0
    for q, gold, _ in QUERIES:
        ids = [h.doc_id for h in idx.search(q, 3)]
        hit += int(gold in ids)
    assert hit / len(QUERIES) >= 0.8


def test_heldout_paraphrase_recall() -> None:
    idx = build()
    hit = 0
    for q, gold, _ in HELDOUT_QUERIES:
        ids = [h.doc_id for h in idx.search(q, 3)]
        hit += int(gold in ids)
    assert hit / len(HELDOUT_QUERIES) >= 0.8


def test_chunking_overlap() -> None:
    idx = Index(chunk_size=50, overlap=10)
    idx.build(["a" * 120])
    assert len(idx.chunks) == 3
    assert idx.chunks[0][-10:] == idx.chunks[1][:10]


def test_invalid() -> None:
    with pytest.raises(ValueError):
        Index(chunk_size=10, overlap=10)
    idx = Index()
    with pytest.raises(RuntimeError):
        idx.search("x")
    with pytest.raises(ValueError):
        idx.build([])
    with pytest.raises(ValueError):
        build().search("", 3)
    with pytest.raises(ValueError):
        build().search("x", 0)
    with pytest.raises(ValueError):
        Pipeline(build(), Generator()).query("x", 3, cite_top_k=0)
