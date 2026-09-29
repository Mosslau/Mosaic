"""迷你 RAG 检索增强生成 — 框架对照调用（流水线族）

流水线族**没有 `run_framework(X_train, X_test, y_train, y_test)` 这种签名**：
对照对象是"同一套语料与问题的端到端链路结果"，而不是某个框架的一行调用。

两级对照，从易到难（README「框架对照」段两者都要写）：
  ① 检索环节对照（不需要 API key，随时可跑）
     手写向量检索 vs 现成检索基线（BM25 / 关键词）——量化召回率与 MRR 的差别
  ② 生成环节对照（需要模型服务；无凭据时标「未在本环境验证」）
     手写提示词组装 vs 现成 RAG 链（如 LangChain 的 retriever+LLM 链）——
     量化端到端答案质量与耗时，并说明现成链替你做了什么（分块、去重、重排、上下文裁剪）
"""


def run_retrieval_baseline(index, queries, top_k: int = 3):
    """① 检索环节对照：返回与手写检索对齐的指标字典。

    返回示例：{"recall@k": ..., "mrr": ..., "time_sec": ...}
    """
    # TODO: 例：用 rank_bm25 / sklearn 的 TfidfVectorizer 做词法检索基线，
    #   与 Index.search 在同一批 queries 上比 recall@k 与 MRR。
    #   README 要分析：向量检索在什么问法上赢、什么问法上输给词法检索。
    raise NotImplementedError("TODO: 实现检索基线并返回对齐指标")


def run_pipeline_baseline(queries, references):
    """② 生成环节对照：跑一条现成 RAG 链，返回端到端指标。

    返回示例：{"answer_match": ..., "time_sec": ...}
    """
    # TODO: 例：LangChain 的检索链；**无 API key 时不要伪造结果**，
    #   按纪律 ⑤ 标「未在本环境验证」并写明缺什么、读者怎么验证。
    raise NotImplementedError("TODO: 实现端到端基线并返回对齐指标")


if __name__ == "__main__":
    raise SystemExit("请先完成 run_retrieval_baseline，由 demo.py 统一调用对比")
