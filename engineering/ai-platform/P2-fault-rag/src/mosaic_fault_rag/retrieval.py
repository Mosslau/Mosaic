"""最小检索：字符 unigram/bigram + TF-IDF 余弦相似度。

为什么不用向量库：D2/D3 的向量检索属于 AI 平台正式能力；本纵切先证明
「故障 → 依据 → 带引用的答案」这条链，检索器可替换（Milvus/faiss 后续接入）。
中文不分词，用字符 bigram 近似，避免引入分词依赖。
"""

import math
import re
from collections import Counter
from typing import Any, Dict, List

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> List[str]:
    lowered = text.lower()
    latin = _LATIN.findall(lowered)
    cjk = "".join(_CJK.findall(lowered))
    unigrams = list(cjk)
    bigrams = [cjk[i:i + 2] for i in range(len(cjk) - 1)]
    return latin + unigrams + bigrams


class Retriever:
    def __init__(self, docs: List[Dict[str, Any]]):
        self.docs = docs
        self._token_counts = [
            Counter(tokenize("%s %s %s" % (doc["title"], doc["text"], " ".join(doc.get("fault_codes", [])))))
            for doc in docs
        ]
        doc_freq: Counter = Counter()
        for counts in self._token_counts:
            for term in counts:
                doc_freq[term] += 1
        total = max(len(docs), 1)
        self._idf = {term: math.log((total + 1) / (freq + 1)) + 1 for term, freq in doc_freq.items()}
        self._default_idf = math.log(total + 1) + 1
        self._vectors = [self._vector(counts) for counts in self._token_counts]

    def _weight(self, term: str, count: int) -> float:
        return (1 + math.log(count)) * self._idf.get(term, self._default_idf)

    def _vector(self, counts: Counter) -> Dict[str, float]:
        raw = {term: self._weight(term, count) for term, count in counts.items()}
        norm = math.sqrt(sum(value * value for value in raw.values())) or 1.0
        return {term: value / norm for term, value in raw.items()}

    def _query_vector(self, query: str) -> Dict[str, float]:
        counts = Counter(tokenize(query))
        raw = {term: self._weight(term, count) for term, count in counts.items()}
        norm = math.sqrt(sum(value * value for value in raw.values())) or 1.0
        return {term: value / norm for term, value in raw.items()}

    def search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        query_vector = self._query_vector(query)
        scored = []
        for doc, vector in zip(self.docs, self._vectors):
            score = sum(query_vector.get(term, 0.0) * weight for term, weight in vector.items())
            scored.append((round(score, 6), doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [{"doc": doc, "score": score} for score, doc in scored[:top_k]]
