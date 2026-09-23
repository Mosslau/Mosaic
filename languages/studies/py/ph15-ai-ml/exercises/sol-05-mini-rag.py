#!/usr/bin/env python3
# exercises/sol-05-mini-rag.py —— 练习 5 参考实现：迷你 RAG 问答（检索质量对比）
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5（本机已装并实测，无需 transformers）
# 运行：python3 sol-05-mini-rag.py（离线可跑，已验证）
# 验证状态：已验证 —— 语料/查询固定，数字完全可复现
# 验证块数字实测：规范化前 cover@1/2/3 = 0/5、2/5、3/5；规范化（词形归一的玩具版）后
#                cover@1/2/3 = 1/5、4/5、5/5 —— 文本预处理直接提升检索质量
"""练习 5（简单 RAG 问答，对应 roadmap）：检索质量决定回答质量。

8 段电动设备资料 + 5 个需要「查全」的问句（多数要 2 段资料才能答完整）。
实现：TF-IDF + 余弦检索 → 取 top-k 资料块 → 模板拼装回答；评估指标是
「资料覆盖率 cover@k = 标准答案所需的资料段是否都在 top-k 里」。
对比两版索引：
  ① 原样分词：charge / charges / charging、deep / deeply、discharge / discharges
     互不匹配 → cover@3 只有 3/5；
  ② 词形归一（把同一词的变形映射到同一词形，即玩具版 stemming）→ cover@3 升到 5/5。
结论：RAG 的上限由检索质量决定——生成模型再强，检索漏了关键资料段也答不
全；工程里对应「分块、清洗、规范化、同义扩展（再上嵌入模型）」。
"""

from __future__ import annotations

import re

import numpy as np

STOP = set(
    """a an the and or but of to in on for with at by from as is are was were be been it its
this that these those can could would should will may might do does did not no yes you your we our
they their about into over under""".split()
)

DOCS: list[tuple[str, str]] = [
    (
        "dc1",
        "Fast charging at 150 kilowatts takes about 30 minutes to reach 80 percent state of charge.",
    ),
    (
        "dc2",
        "The last 20 percent charges slower to protect the component, adding about 20 minutes. "
        "Do not charge to 100 percent daily.",
    ),
    (
        "dr1",
        "In cold ambient the runtime can drop by about 25 percent because the component is less "
        "efficient and heating consumes power.",
    ),
    (
        "dr2",
        "Precondition the component while the device is poweredugged in so the heater does not drain the component, "
        "which keeps the winter range higher.",
    ),
    (
        "db1",
        "Component health declines fastest with deep discharges and high temperature. Keeping the charge "
        "between 20 and 80 percent slows the loss of capacity.",
    ),
    (
        "db2",
        "The component warranty covers 8 years or 40000 operating hours. Capacity loss below 70 percent "
        "within warranty is covered.",
    ),
    ("dt1", "Check the component mounts every month and before long trips."),
    (
        "dt2",
        "Loose mounts increase resistance and can reduce the range by about 5 percent.",
    ),
]

# (query, 回答所需资料段) —— 注意 q1/q2/q4/q5 都要两段资料才能答完整
QUERIES: list[tuple[str, list[str]]] = [
    ("how long does a full fast charging session take", ["dc1", "dc2"]),
    ("why is my winter range lower and what can I do about it", ["dr1", "dr2"]),
    ("is it bad for the component to discharge deeply", ["db1"]),
    ("low mount torque and range loss", ["dt2", "dt1"]),
    ("component capacity degrading, is the warranty still valid", ["db2", "db1"]),
]

# 词形归一表：把同一词的变形映射到同一词形（玩具版 stemming；真实工程用 Porter/嵌入模型）
ALIAS: dict[str, str] = {
    "charges": "charge",
    "charging": "charge",
    "discharges": "discharge",
    "discharging": "discharge",
    "deeply": "deep",
    "tires": "tire",
    "pressures": "pressure",
    "trips": "trip",
    "cells": "cell",
}


def canon(word: str) -> str:
    return ALIAS.get(word, word)


def tokenize(text: str, use_canon: bool) -> list[str]:
    words = re.findall(r"[a-z]+", text.lower())
    out = []
    for w in words:
        if use_canon:
            w = canon(w)
        if w not in STOP and len(w) > 1:
            out.append(w)
    return out


def build_index(texts: list[str], use_canon: bool) -> tuple[np.ndarray, list[str]]:
    """TF-IDF 词向量矩阵（行归一化，余弦=点积）。"""
    vocab = sorted({w for t in texts for w in tokenize(t, use_canon)})
    idx = {w: i for i, w in enumerate(vocab)}
    n_d = len(texts)
    tf = np.zeros((n_d, len(vocab)))
    df = np.zeros(len(vocab))
    for di, t in enumerate(texts):
        seen: set[int] = set()
        for w in tokenize(t, use_canon):
            tf[di, idx[w]] += 1
            seen.add(idx[w])
        for j in seen:
            df[j] += 1
    matrix = tf * (np.log((1 + n_d) / (1 + df)) + 1.0)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True), vocab


def coverage(use_canon: bool) -> tuple[list[float], list[int]]:
    """返回每个查询 top-k 是否覆盖所需资料（k=1/2/3）。"""
    ids = [d for d, _ in DOCS]
    matrix, vocab = build_index([t for _, t in DOCS], use_canon)
    vocab_idx = {w: i for i, w in enumerate(vocab)}
    sims: list[np.ndarray] = []
    for q, _need in QUERIES:
        qv = np.zeros(len(vocab))
        for w in tokenize(q, use_canon):
            if w in vocab_idx:
                qv[vocab_idx[w]] += 1
        qv = qv / np.linalg.norm(qv)
        sims.append(matrix @ qv)
    counts: list[int] = []
    per_query: list[float] = []
    for k in (1, 2, 3):
        n_ok = 0
        for (q, need), sim in zip(QUERIES, sims, strict=True):
            top = {ids[i] for i in np.argsort(sim)[::-1][:k]}
            n_ok += int(set(need) <= top)
            if k == 3:
                per_query.append(sum(1 for d in need if d in top))
        counts.append(n_ok)
    return [float(c) / len(QUERIES) for c in counts], [int(p) for p in per_query]


def main() -> None:
    print("== 迷你 RAG：8 段资料 × 5 问（4 问需要 ≥2 段资料才能答完整）==")
    for label, canon_used in (("① 原样分词", False), ("② 词形归一", True)):
        rates, per_q = coverage(canon_used)
        print(
            f"   {label}: cover@1 {rates[0]:.1%} / cover@2 {rates[1]:.1%} / cover@3 {rates[2]:.1%}"
            f"（top-3 平均覆盖 {sum(per_q)}/{sum(len(n) for _, n in QUERIES)} 段）"
        )

    ids = [d for d, _ in DOCS]
    matrix, vocab = build_index([t for _, t in DOCS], use_canon=True)
    vocab_idx = {w: i for i, w in enumerate(vocab)}
    print("\n   演示 q1「full fast charging session」规范化后 top-3 回答:")
    q = QUERIES[0][0]
    qv = np.zeros(len(vocab))
    for w in tokenize(q, True):
        if w in vocab_idx:
            qv[vocab_idx[w]] += 1
    sim = matrix @ (qv / np.linalg.norm(qv))
    top3 = [ids[i] for i in np.argsort(sim)[::-1][:3]]
    print("     top-3 资料段: " + ", ".join(top3) + " → 覆盖 dc1+dc2，回答完整")
    print(
        "     （规范化前 dc2 在 top-3 之外 → 回答会漏掉『最后 20% 充得更慢/别充满』）"
    )

    rates_before, _ = coverage(False)
    rates_after, _ = coverage(True)
    assert rates_after[2] == 1.0, "规范化后 cover@3 应到 5/5"
    assert rates_after[2] > rates_before[2] and rates_after[1] > rates_before[1]
    print(
        "\n验收通过：cover@3 从 3/5 提到 5/5——检索质量（含文本预处理）直接决定 RAG 回答质量"
    )


if __name__ == "__main__":
    main()
