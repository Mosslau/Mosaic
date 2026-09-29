"""迷你 RAG 检索增强生成 — 手写实现（流水线）

**流水线族没有单一的 Model 接口**：RAG 是一条链路，按环节组织而不是 fit(X, y)。
本目录的形态由链路决定，三个环节各自是独立可测的单元：

    index = Index()                      # ① 建索引
    index.build(docs)
    hits  = index.search(query, top_k=3) # ② 检索
    pipe  = Pipeline(index, generator)   # ③ 检索 → 生成
    answer = pipe.query("...")

  环节          类 / 函数           接口
  ----------    ----------------    --------------------------------------
  ① 向量化+索引  Index.build         build(docs) -> None
  ① 检索         Index.search        search(query, top_k) -> list[Hit]
  ③ 生成         Generator.generate  generate(query, contexts) -> str
  ③ 端到端       Pipeline.query      query(text) -> Answer（含引用）

手写纪律（按族细化）：本环节允许复用**本仓库其他实验已完成的手写算法**
（如用 p04 的 attention 做 Rerank），但**禁止直接调 LangChain 等框架的现成链**。
embedding 若用现成模型需在 README 标注出处；否则用词袋 / n-gram 哈希手写降级版。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class Embedder(Protocol):
    """向量化端口：把文本转成稠密向量。手写降级版或现成模型都实现这个协议。"""

    def encode(self, texts: list[str]) -> Any: ...


@dataclass
class Hit:
    """一条检索结果：原文 + 相似度分数 + 在原文中的位置（引用溯源要用）。"""

    text: str
    score: float
    doc_id: int = -1


@dataclass
class Answer:
    """端到端产物：答案 + 引用的原文片段（**引用溯源是 RAG 的验收项之一**）。"""

    text: str
    citations: list[Hit] = field(default_factory=list)


class Index:
    """① 向量化并建索引 + ② 检索。两个环节耦合在索引结构里，但接口分开。"""

    def __init__(self, embedder: Embedder | None = None, chunk_size: int = 200) -> None:
        self.embedder = embedder
        self.chunk_size = chunk_size
        self.chunks: list[str] = []
        self.vectors: Any = None

    def build(self, docs: list[str]) -> None:
        """切块 → 向量化 → 存成矩阵（同时保留 chunk 原文，供引用回填）。"""
        # TODO: 手写
        #   1. 按 chunk_size 切块（重叠多少自己定，README 说明它对召回的影响）
        #   2. 逐块 encode；堆成 (n_chunks, dim) 矩阵
        #   3. 归一化后存起来（这样内积就等于余弦相似度，检索更快）
        raise NotImplementedError("TODO: 手写切块 + 向量化 + 索引")

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        # TODO: 手写——query 向量化后与索引做内积，取 top_k（对照基线：关键词/BM25 检索）
        raise NotImplementedError("TODO: 手写向量检索")


class Generator:
    """③ 生成环节：把手写版与对照版都收在同一个 generate 接口下。"""

    def __init__(self, llm: Callable[[str], str] | None = None) -> None:
        self.llm = llm

    def generate(self, query: str, contexts: list[Hit]) -> str:
        """把 contexts 拼进提示词后交给 llm；无 llm 时用可复现的降级实现。"""
        # TODO: 手写
        #   1. 组装提示词：要求"仅依据给定上下文回答，并标注来源"
        #   2. self.llm 为 None 时退化成"抽取式"回答（直接返回最相关片段），
        #      这样 demo 无需 API key 也能跑通端到端——README 要标注这是降级口径
        raise NotImplementedError("TODO: 手写提示词组装与生成")


class Pipeline:
    """端到端：query → 检索 → 生成 → 带引用的 Answer。"""

    def __init__(self, index: Index, generator: Generator) -> None:
        self.index = index
        self.generator = generator

    def query(self, text: str, top_k: int = 3) -> Answer:
        # TODO: 手写——index.search 拿 contexts，generator.generate 出答案，
        #   把用到的 Hit 作为 citations 回填（引用溯源是验收项，不能只返回字符串）
        raise NotImplementedError("TODO: 手写端到端链路")


if __name__ == "__main__":
    raise SystemExit("请先完成 Index.build / search 与 Pipeline.query，再到 demo.py 跑实验")
