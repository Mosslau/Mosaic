#!/usr/bin/env python3
# examples/ex06-mini-rag.py —— 迷你 RAG：检索质量决定回答质量（主文档 3.10）
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5（本机已装并实测；无需 transformers / 向量库）
# 运行：python3 ex06-mini-rag.py（离线可跑，已验证）
# 验证状态：已验证 —— 全部数字为固定语料 / 查询下的本机实测，完全可复现
# 验证块数字实测：8 问中清晰措辞 6 问 hit@1 全中、模糊 2 问全 miss → hit@1 6/8；
#                top-3 上下文救回 1 问（battery query）→ hit@3 7/8；停用词不移除时
#                词频检索 hit@1 5/8（TF-IDF 6/8）；句子级分块 hit@1 同样 6/8
"""迷你 RAG 检索质量演示（roadmap 必会概念：RAG 要关注检索质量）。

在 12 段内置的电动车手册语料上，用「词袋 / TF-IDF + 余弦相似度」手工实现检索，
对比不同检索方案与查询措辞的命中率，并演示「检索错了，生成再强也答错」：
  A. 查询措辞决定检索质量：措辞清晰 6 问 top1 全中；「battery seems weak and
     drains fast」这类模糊问法，top1 命中文不对题的充电文档；
  B. top-k 是补救手段：把 top-3 上下文都给生成器，有一问救回（hit@3 7/8），
     但完全失败的一问（car range → 冬季续航文档）仍在 top-3 之外；
  C. 检索函数与预处理：停用词不移除时词频检索 5/8 vs TF-IDF 6/8——先做对
     预处理与查询，再谈更 fancy 的嵌入模型（嵌入与向量库概念见主文档 3.10）。
语料与查询用英文，避免引入中文分词依赖（中文方案：jieba 分词或字符 n-gram，
见主文档 3.10）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

# 停用词表（超高频功能词，对「充电」「续航」这类主题几乎无区分力）
STOP = set(
    """a an the and or but of to in on for with at by from as is are was were be been it its
this that these those can could would should will may might do does did not no yes you your we our
they their about into over under""".split()
)

# 语料：(文档 id, 主题, 正文)。正文即「资料库」——真实 RAG 里这里是文档库的切块
CORPUS: list[tuple[str, str, str]] = [
    (
        "doc_chg_1",
        "充电",
        "Fast charging at 150 kilowatts takes about 30 minutes to reach 80 percent "
        "state of charge. The last 20 percent charges slower to protect the battery cells.",
    ),
    (
        "doc_chg_2",
        "充电",
        "Avoid charging to 100 percent every day for daily driving. The recommended "
        "daily limit is 80 percent because high state of charge accelerates battery aging.",
    ),
    (
        "doc_chg_3",
        "充电",
        "Home charging with a 7 kilowatt AC wallbox adds about 40 kilometers of range "
        "per hour. An overnight charge from empty to full takes about 9 hours.",
    ),
    (
        "doc_bat_1",
        "电池",
        "Battery health measured as state of health declines fastest with deep "
        "discharges and high temperature. Keeping the battery between 20 and 80 percent "
        "slows the loss of capacity.",
    ),
    (
        "doc_bat_2",
        "电池",
        "The battery warranty covers 8 years or 160000 kilometers, whichever comes "
        "first. Capacity loss below 70 percent within the warranty period is covered.",
    ),
    (
        "doc_rng_1",
        "续航",
        "Driving range depends on speed, cabin heating and cooling, and ambient "
        "temperature. Highway driving at 120 kilometers per hour consumes about 30 "
        "percent more energy than city driving.",
    ),
    (
        "doc_rng_2",
        "续航",
        "In cold weather the range can drop by 25 percent because the battery is less "
        "efficient and the cabin heater uses power. Preconditioning the cabin while the "
        "car is plugged in preserves range.",
    ),
    (
        "doc_regen_1",
        "驾驶",
        "Regenerative braking recovers energy and converts it back into the battery. "
        "One pedal driving uses the electric motor to slow the car and extend the range "
        "in the city.",
    ),
    (
        "doc_mnt_1",
        "保养",
        "Check tire pressure every month and before long trips. Low tire pressure "
        "increases rolling resistance and reduces range by about 5 percent.",
    ),
    (
        "doc_ota_1",
        "软件",
        "Software updates are delivered over the air while the car is parked. The car "
        "must have at least 30 percent battery and a stable internet connection to "
        "install an update.",
    ),
    (
        "doc_safe_1",
        "安全",
        "If the battery temperature exceeds 60 degrees Celsius the system disables "
        "fast charging until it cools down. Thermal runaway protection continuously "
        "monitors all cell groups.",
    ),
    (
        "doc_eco_1",
        "驾驶",
        "Smooth acceleration and steady speed give the best energy economy. Hard "
        "acceleration uses up to 50 percent more energy than gentle driving.",
    ),
]

# 评测查询：(query, 标准答案文档, 措辞类型) —— 前 6 问措辞清晰，后 2 问刻意模糊
QUERIES: list[tuple[str, str, str]] = [
    ("how long does fast charging take to reach 80 percent", "doc_chg_1", "清晰"),
    ("is it ok to charge the car to 100 percent every night", "doc_chg_2", "清晰"),
    ("does cold weather make the range worse", "doc_rng_2", "清晰"),
    ("what does the battery warranty cover", "doc_bat_2", "清晰"),
    ("check my tire pressure how often", "doc_mnt_1", "清晰"),
    ("can i install updates while driving", "doc_ota_1", "清晰"),
    ("battery seems weak and drains fast", "doc_bat_1", "模糊"),
    ("car range", "doc_rng_1", "模糊"),
]


def tokenize(text: str, remove_stop: bool) -> list[str]:
    """小写 + 按字母切词；去掉停用词与单字母词（够用的英文分词）。"""
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if (w not in STOP if remove_stop else True) and len(w) > 1]


@dataclass
class VectorSpace:
    """词袋向量空间：词表 + 词频矩阵与 TF-IDF 矩阵（行已归一化，余弦 = 点积）。"""

    vocab: list[str]
    counts: np.ndarray
    tfidf: np.ndarray

    @classmethod
    def build(cls, docs: list[str], remove_stop: bool) -> VectorSpace:
        toks = [tokenize(d, remove_stop) for d in docs]
        vocab = sorted({t for t in docs for t in tokenize(t, remove_stop)})
        idx = {w: i for i, w in enumerate(vocab)}
        n_d, n_v = len(toks), len(vocab)
        tf = np.zeros((n_d, n_v))
        df = np.zeros(n_v)
        for di, words in enumerate(toks):
            seen: set[int] = set()
            for t in words:
                tf[di, idx[t]] += 1
                seen.add(idx[t])
            for j in seen:
                df[j] += 1
        idf = np.log((1 + n_d) / (1 + df)) + 1.0  # sklearn 同款平滑 idf
        tfidf = tf * idf
        return cls(vocab=vocab, counts=_row_norm(tf), tfidf=_row_norm(tfidf))

    def query(self, q: str, use_tfidf: bool) -> np.ndarray:
        """查询向量与全部文档的点积（行归一化后即余弦相似度）。"""
        qv = np.zeros(len(self.vocab))
        for t in tokenize(q, remove_stop=True):
            if t in self.vocab:
                qv[self.vocab.index(t)] += 1
        if qv.sum() == 0:
            return np.zeros(self.counts.shape[0])
        qv = qv / np.linalg.norm(qv)
        matrix = self.tfidf if use_tfidf else self.counts
        return matrix @ qv


def _row_norm(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)


def topk(gold_ids: list[str], sim: np.ndarray, k: int) -> set[str]:
    order = np.argsort(sim)[::-1][:k]
    return {gold_ids[i] for i in order}


def report_variant(name: str, docs: list[str], gold_ids: list[str], remove_stop: bool) -> None:
    """跑一遍检索并输出逐问明细 + 汇总命中率（区分清晰/模糊两组）。"""
    vs = VectorSpace.build(docs, remove_stop)
    sims = [vs.query(q, use_tfidf=True) for q, _, _ in QUERIES]
    hits1 = hits3 = clear_ok = clear_total = 0
    print(f"\n[{name}] 文档/分块数 {len(docs)}，停用词处理 {'移除' if remove_stop else '不移除'}")
    for (q, gold, kind), sim in zip(QUERIES, sims, strict=True):
        top1 = gold_ids[int(np.argmax(sim))]
        ok1 = top1 == gold
        ok3 = gold in topk(gold_ids, sim, 3)
        hits1 += ok1
        hits3 += ok3
        if kind == "清晰":
            clear_ok += ok1
            clear_total += 1
        print(
            f"   {'命中' if ok1 else '未中'} [{kind}] 「{q}」→ top1 {top1}"
            f"{'' if ok1 else f'（应为 {gold}）'}　sim={float(np.max(sim)):.3f}"
        )
    print(
        f"   hit@1 {hits1}/{len(QUERIES)}（清晰组 {clear_ok}/{clear_total}、模糊组 "
        f"{hits1 - clear_ok}/{len(QUERIES) - clear_total}）/ hit@3 {hits3}/{len(QUERIES)}"
    )


def section_a_b_phrasing_and_topk() -> None:
    print("== A/B. 查询措辞与 top-k 补救（段落级检索，TF-IDF + 停用词移除）==")
    docs = [text for _, _, text in CORPUS]
    gold_ids = [doc_id for doc_id, _, _ in CORPUS]
    report_variant("段落级", docs, gold_ids, remove_stop=True)
    print(
        "   → 清晰措辞 6 问全中；模糊组：battery 问法 top1 答非所问（充电文档），"
        "car range 问法 top1 是冬季续航文档——同主题不同文档在抢答"
    )


def section_c_retrieval_function() -> None:
    print("\n== C. 检索函数与预处理对比（同一批段落，hit@1 命中数）==")
    docs = [text for _, _, text in CORPUS]
    gold_ids = [doc_id for doc_id, _, _ in CORPUS]
    for label, stop in (("不移除停用词", False), ("移除停用词", True)):
        vs = VectorSpace.build(docs, stop)
        h_count = sum(
            1 for q, g, _ in QUERIES if gold_ids[int(np.argmax(vs.query(q, use_tfidf=False)))] == g
        )
        h_tfidf = sum(
            1 for q, g, _ in QUERIES if gold_ids[int(np.argmax(vs.query(q, use_tfidf=True)))] == g
        )
        print(f"   {label}: 词频计数 {h_count}/8 vs TF-IDF {h_tfidf}/8")
    print(
        "   → 先做对预处理（停用词、清洗）收益最直接；小语料上词频与 TF-IDF 差距有限，"
        "嵌入模型与向量库是更大语料/语义检索时的升级（主文档 3.10）"
    )


def section_d_chunking() -> None:
    print("\n== D. 检索粒度：句子级分块（24 块）==")
    sentences: list[str] = []
    sent_gold: list[str] = []
    for doc_id, _, text in CORPUS:
        for s in re.split(r"(?<=[.!?]) ", text):
            s = s.strip()
            if s:
                sentences.append(s)
                sent_gold.append(doc_id)
    report_variant("句子级", sentences, sent_gold, remove_stop=True)


def section_e_rag_assembly() -> None:
    print("\n== E. 组装成 RAG 问答：检索错了，生成再强也答错 ==")
    docs = [text for _, _, text in CORPUS]
    gold_ids = [doc_id for doc_id, _, _ in CORPUS]
    CORPUS_IDS = gold_ids
    vs = VectorSpace.build(docs, remove_stop=True)
    topic = {doc_id: t for doc_id, t, _ in CORPUS}
    for q, gold, kind in QUERIES:
        if kind != "模糊":
            continue
        sim = vs.query(q, use_tfidf=True)
        order = np.argsort(sim)[::-1]
        top1 = gold_ids[order[0]]
        top3_docs = [gold_ids[order[i]] for i in range(3)]
        ok1 = top1 == gold
        ok3 = gold in top3_docs
        print(f"   问「{q}」（应来自 {gold}，主题『{topic[gold]}』）")
        print(
            f"     top1 上下文来自 {top1}（主题『{topic[top1]}』）→ "
            f"答案 {'正确' if ok1 else '大概率答非所问'}"
        )
        print(
            "     top3 含标准文档？"
            + (
                "是 —— 已在 top-3 里，把 3 段都给生成器能救回"
                if ok3
                else "否 —— 检索彻底失败，RAG 必错"
            )
        )
        if ok3:
            print(f"     （{gold} 在第 {order.tolist().index(CORPUS_IDS.index(gold)) + 1} 顺位）")


if __name__ == "__main__":
    print("迷你 RAG：12 段电动车手册语料 × 8 个评测问句（6 清晰 + 2 模糊）")
    section_a_b_phrasing_and_topk()
    section_c_retrieval_function()
    section_d_chunking()
    section_e_rag_assembly()
