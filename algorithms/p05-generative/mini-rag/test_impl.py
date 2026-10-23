"""RAG — 性质测试（pytest）"""

import pytest
from demo import DOCS, QUERIES
from impl import Generator, Index, Pipeline


def build():
    return Index(chunk_size=200, overlap=40).build(DOCS)


def test_build_chunks_and_vectors() -> None:
    idx = build()
    assert len(idx.chunks) == len(DOCS)
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
    assert a.citations and 1 in [c.doc_id for c in a.citations]
    assert "UCB1" in a.text


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
