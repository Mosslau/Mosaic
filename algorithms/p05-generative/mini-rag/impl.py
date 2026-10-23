"""迷你 RAG — 手写实现（流水线）

    idx = Index().build(docs)
    hits = idx.search("...", top_k=3)
    pipe = Pipeline(idx, Generator())
    ans = pipe.query("...")       # Answer(text, citations)
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> Any: ...


@dataclass
class Hit:
    text: str
    score: float
    doc_id: int = -1


@dataclass
class Answer:
    text: str
    citations: list[Hit] = field(default_factory=list)


STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "by", "as", "at", "from", "that",
    "this", "it", "its", "which", "what", "when", "how", "does", "do",
    "use", "uses", "using", "can", "will", "into", "than", "then",
}


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in STOPWORDS]


def _stable_hash(token: str, dim: int) -> int:
    h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "little") % dim


class HashingEmbedder:
    """手写 TF-IDF + 哈希向量；无需外部 embedding 模型。"""

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.idf: dict[str, float] = {}
        self.n_docs = 0

    def fit(self, texts: list[str]) -> HashingEmbedder:
        df = Counter()
        for t in texts:
            df.update(set(tokenize(t)))
        self.n_docs = len(texts)
        self.idf = {w: np.log((self.n_docs + 1) / (c + 1)) + 1 for w, c in df.items()}
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim))
        for i, text in enumerate(texts):
            tf = Counter(tokenize(text))
            for w, c in tf.items():
                weight = (1 + np.log(c)) * self.idf.get(w, 1.0)
                out[i, _stable_hash(w, self.dim)] += weight
        norm = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.maximum(norm, 1e-12)


class Index:
    def __init__(self, embedder: Embedder | None = None, chunk_size: int = 200,
                 overlap: int = 40) -> None:
        if chunk_size < 1 or not (0 <= overlap < chunk_size):
            raise ValueError("需要 chunk_size>=1 且 0<=overlap<chunk_size")
        self.embedder = embedder or HashingEmbedder()
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: list[str] = []
        self.doc_ids: list[int] = []
        self.vectors: np.ndarray | None = None

    def _split(self, doc: str) -> list[str]:
        doc = doc.strip()
        if len(doc) <= self.chunk_size:
            return [doc] if doc else []
        out, start = [], 0
        while start < len(doc):
            out.append(doc[start:start + self.chunk_size])
            if start + self.chunk_size >= len(doc):
                break
            start += self.chunk_size - self.overlap
        return out

    def build(self, docs: list[str]) -> Index:
        self.chunks, self.doc_ids = [], []
        for i, doc in enumerate(docs):
            for chunk in self._split(doc):
                self.chunks.append(chunk)
                self.doc_ids.append(i)
        if not self.chunks:
            raise ValueError("docs 不能为空")
        if hasattr(self.embedder, "fit"):
            self.embedder.fit(self.chunks)
        self.vectors = np.asarray(self.embedder.encode(self.chunks), dtype=float)
        return self

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        if self.vectors is None:
            raise RuntimeError("请先 build")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query 不能为空")
        if top_k < 1:
            raise ValueError("top_k 必须 >=1")
        q = np.asarray(self.embedder.encode([query])[0], dtype=float)
        scores = self.vectors @ q
        order = np.argsort(scores)[::-1][:top_k]
        return [Hit(self.chunks[i], float(scores[i]), self.doc_ids[i]) for i in order]


class Generator:
    def __init__(self, llm: Callable[[str], str] | None = None) -> None:
        self.llm = llm

    def generate(self, query: str, contexts: list[Hit]) -> str:
        if not contexts:
            return "未找到相关上下文。"
        if self.llm is not None:
            prompt = ("仅依据以下上下文回答问题，并标注来源。\n"
                      + "\n".join(f"[doc {c.doc_id}] {c.text}" for c in contexts)
                      + f"\n问题：{query}\n答案：")
            return self.llm(prompt)
        # 无 LLM 的抽取式降级：直接返回最相关片段并标注 doc id
        return f"{contexts[0].text} [doc {contexts[0].doc_id}]"


class Pipeline:
    def __init__(self, index: Index, generator: Generator) -> None:
        self.index = index
        self.generator = generator

    def query(self, text: str, top_k: int = 3) -> Answer:
        hits = self.index.search(text, top_k)
        return Answer(self.generator.generate(text, hits), hits)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
