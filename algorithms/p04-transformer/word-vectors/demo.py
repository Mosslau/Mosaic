"""词向量 — demo：同一份合成语料上双跑 skip-gram+负采样 与 PPMI-SVD 基线。

语料是模板生成的**合成语料**（非真实语料）：国家-首都、男-女、单-复数、现在-过去
四组语义关系 + 填充句子，词表 94，语料约 3.3 万 token，种子固定，可逐位复现。
"""

from __future__ import annotations

import time

import numpy as np

from baseline import PPMISVD
from impl import SkipGramNS, l2_normalize

# ---------- 合成语料 ----------

COUNTRIES = [("valdoria", "valport"), ("kestry", "kesthaven"), ("morvane", "morvik"),
             ("ashkara", "ashfall"), ("belmoor", "belcrest"), ("corvani", "corvale"),
             ("dunmarch", "dunhold"), ("eldoray", "elmshore"), ("ferronia", "ferrow"),
             ("galmira", "galston")]
GENDERS = [("king", "queen"), ("prince", "princess"), ("father", "mother"),
           ("brother", "sister"), ("uncle", "aunt"), ("son", "daughter")]
PLURALS = [("cat", "cats"), ("dog", "dogs"), ("book", "books"),
           ("river", "rivers"), ("table", "tables"), ("garden", "gardens")]
TENSES = [("walk", "walked"), ("play", "played"), ("cook", "cooked"),
          ("open", "opened"), ("jump", "jumped"), ("watch", "watched")]

NOISE = ["story", "market", "morning", "evening", "city", "country", "day", "year"]

# 模板只使用词表内的词：每个关系对都在**同一组句子框架**里出现，
# 关系方向因此有机会表现为一个稳定的向量偏移（a:b :: c:d 的基础）。
COUNTRY_TEMPLATES = [
    "the capital of {C} is {K}",
    "{K} is the capital city of {C}",
    "people travel from {C} to {K} in the morning",
    "{C} and {K} are in this story",
    "{C} is a country and the capital is {K}",
]
GENDER_TEMPLATES = [
    "the {M} and the {F} are in the market",
    "he is the {M} and she is the {F}",
    "the {M} is a man and the {F} is a woman",
    "the {M} is with his people and the {F} is with her people",
]
PLURAL_TEMPLATES = [
    "one {S} and two {P}",
    "the {S} is in the market and the {P} are in the city",
    "a {S} is new and many {P} are new",
    "this {S} and that {P} are in the story",
]
TENSE_TEMPLATES = [
    "people {PR} today and people {PA} yesterday",
    "the people {PR} now and the people {PA} then",
    "people {PR} in the morning and people {PA} in the evening",
    "this day people {PR} and that day people {PA}",
]
NOISE_TEMPLATES = [
    "the {f1} is in the {f2}",
    "{f1} and {f2} are in this {f3}",
    "people in the {f1} are new",
    "a {f1} is in the city",
    "the {f1} was in the market with the {f2}",
    "this {f1} and that {f2} are in the story",
]


def build_corpus(seed=0, reps=(22, 28, 28, 28), n_filler=800):
    """生成合成语料：返回 (sentences, meta)。固定 seed 下逐 token 可复现。"""
    rng = np.random.default_rng(seed)
    sents = []
    for _ in range(reps[0]):
        for C, K in COUNTRIES:
            for tpl in COUNTRY_TEMPLATES:
                sents.append(tpl.format(C=C, K=K).split())
    for _ in range(reps[1]):
        for M, F in GENDERS:
            for tpl in GENDER_TEMPLATES:
                sents.append(tpl.format(M=M, F=F).split())
    for _ in range(reps[2]):
        for S, P in PLURALS:
            for tpl in PLURAL_TEMPLATES:
                sents.append(tpl.format(S=S, P=P).split())
    for _ in range(reps[3]):
        for PR, PA in TENSES:
            for tpl in TENSE_TEMPLATES:
                sents.append(tpl.format(PR=PR, PA=PA).split())
    for _ in range(n_filler):
        tpl = NOISE_TEMPLATES[int(rng.integers(len(NOISE_TEMPLATES)))]
        n_f = tpl.count("{f")
        f = list(rng.choice(NOISE, size=n_f, replace=False))
        sents.append(tpl.format(f1=f[0], f2=f[1] if n_f > 1 else f[0],
                                f3=f[2] if n_f > 2 else f[0]).split())
    rng.shuffle(sents)                      # 打乱句序，避免同模板连续出现
    tokens = sum(len(s) for s in sents)
    meta = {"sentences": len(sents), "tokens": tokens,
            "vocab": len({w for s in sents for w in s}), "seed": seed}
    return sents, meta


# ---------- 评估 ----------

RELATION_SETS = [
    ("country-capital", COUNTRIES),
    ("male-female", GENDERS),
    ("singular-plural", PLURALS),
    ("present-past", TENSES),
]
GROUP_OF, PARTNER_OF, SIDES = {}, {}, {}
for _name, _pairs in RELATION_SETS:
    for _a, _b in _pairs:
        GROUP_OF[_a] = f"{_name}:左"
        GROUP_OF[_b] = f"{_name}:右"
        PARTNER_OF[_a], PARTNER_OF[_b] = _b, _a
    SIDES.setdefault(_name, ([a for a, _ in _pairs], [b for _, b in _pairs]))


def analogy_items():
    """a:b :: c:? 的测试题。按关系对组合 3:1 确定性切分开发集/留出集。

    留出的是**测试关系对组合**（同一个 (i,j) 只出现在一侧），不是词——词都在语料里，
    否则点积无从计算。调参只看开发集，留出集只在 demo 里报一次数。
    """
    items = []
    for r, (name, pairs) in enumerate(RELATION_SETS):
        for i, (a, b) in enumerate(pairs):
            for j, (c, d) in enumerate(pairs):
                if i == j:
                    continue
                split = "heldout" if (i * 5 + j * 3 + r) % 4 == 0 else "dev"
                items.append({"rel": name, "a": a, "b": b, "c": c, "d": d, "split": split})
    return items


def analogy_top1(vectors, word2id, items):
    """3CosAdd：target = v(b)-v(a)+v(c)，全词表余弦排序，排除 a/b/c 后取 top-1。"""
    if not items:
        return float("nan")
    V = l2_normalize(np.asarray(vectors, float))
    idx = np.array([[word2id[it[k]] for k in "abcd"] for it in items])
    target = l2_normalize(V[idx[:, 1]] - V[idx[:, 0]] + V[idx[:, 2]])
    scores = target @ V.T
    rows = np.arange(len(items))
    scores[rows[:, None], idx[:, :3]] = -np.inf       # 排除查询里的三个词
    return float((scores.argmax(1) == idx[:, 3]).mean())


def nn_purity(vectors, vocab, word2id, topk=5):
    """最近邻纯度：关系词的 top-k 邻居里同类别（同关系的同一侧）的比例。

    候选是全部词，但排除自身与**配对词**——配对词是训练时直接同现的正样本，
    不排除的话纯度衡量的是"记没记住配对"，而不是类别结构（类比题已经覆盖前者）。
    """
    V = l2_normalize(np.asarray(vectors, float))
    label = np.array([GROUP_OF.get(w, "") for w in vocab])
    words = [w for w in vocab if w in GROUP_OF]
    ids = np.array([word2id[w] for w in words])
    scores = V @ V[ids].T
    for col, w in enumerate(words):
        scores[word2id[w], col] = -np.inf
        if PARTNER_OF[w] in word2id:
            scores[word2id[PARTNER_OF[w]], col] = -np.inf
    top = np.argsort(-scores, axis=0)[:topk]
    return float((label[top] == label[ids][None, :]).mean())


def same_side_cosine(vectors, word2id):
    """同侧词两两余弦的均值：越高说明同角色词越塌缩成一个点（表示丢失了区分度）。"""
    V = l2_normalize(np.asarray(vectors, float))
    vals = []
    for _, (left, right) in SIDES.items():
        for side in (left, right):
            X = V[[word2id[w] for w in side]]
            vals.append((X @ X.T)[np.triu_indices(len(side), 1)])
    return float(np.concatenate(vals).mean())


def evaluate(vectors, vocab, word2id, items):
    dev = [it for it in items if it["split"] == "dev"]
    held = [it for it in items if it["split"] == "heldout"]
    return {"analogy_dev": analogy_top1(vectors, word2id, dev),
            "analogy_heldout": analogy_top1(vectors, word2id, held),
            "purity": nn_purity(vectors, vocab, word2id),
            "same_side_cos": same_side_cosine(vectors, word2id),
            "n_dev": len(dev), "n_heldout": len(held)}


# ---------- 双跑 ----------

def run(dims=(16, 32, 64), seed=0, epochs=40, negative=5):
    """训练两种方法并评估；返回结果与模型（素材脚本复用同一份结果）。"""
    sentences, meta = build_corpus(seed)
    items = analogy_items()
    out = {"corpus": meta, "items": {"total": len(items)}, "impl": {}, "baseline": {},
           "models": {"impl": {}, "baseline": {}}}
    for dim in dims:
        t0 = time.perf_counter()
        m = SkipGramNS(dim=dim, epochs=epochs, negative=negative, seed=seed).fit(sentences)
        dt = time.perf_counter() - t0
        out["impl"][dim] = evaluate(m.vectors, m.vocab, m.word2id, items)
        out["impl"][dim].update({"seconds": dt, "pairs": m.n_pairs,
                                 "tokens": m.n_tokens, "loss": list(m.loss_history)})
        out["models"]["impl"][dim] = m

        t0 = time.perf_counter()
        b = PPMISVD(dim=dim, seed=seed).fit(sentences)
        dt = time.perf_counter() - t0
        out["baseline"][dim] = evaluate(b.vectors, b.vocab, b.word2id, items)
        out["baseline"][dim].update({"seconds": dt})
        out["models"]["baseline"][dim] = b
    return out


def main() -> None:
    res = run()
    c = res["corpus"]
    print(f"合成语料（非真实语料）：{c['sentences']} 句 / {c['tokens']} token / "
          f"词表 {c['vocab']} / seed {c['seed']}")
    print(f"类比题：开发 {res['impl'][32]['n_dev']} 题，留出 {res['impl'][32]['n_heldout']} 题"
          f"（3CosAdd top-1）")
    print("\n dim | 方法      | 留出类比 | 开发类比 | 最近邻纯度 | 同侧余弦 | 耗时")
    for dim in (16, 32, 64):
        for tag, key in (("SGNS", "impl"), ("PPMI-SVD", "baseline")):
            r = res[key][dim]
            print(f" {dim:3d} | {tag:9s} | {r['analogy_heldout']:.3f}    | "
                  f"{r['analogy_dev']:.3f}    | {r['purity']:.3f}      | "
                  f"{r['same_side_cos']:.3f}    | {r['seconds']:.1f}s")
    m32 = res["models"]["impl"][32]
    b32 = res["models"]["baseline"][32]
    print(f"\nSGNS 32 维：king 的近邻 {m32.most_similar('king', 5)}")
    print(f"SGNS 32 维：valdoria:valport :: kestry:? → "
          f"{m32.analogy('valdoria', 'valport', 'kestry', 1)}")
    print(f"PPMI-SVD 32 维：valdoria 的近邻 {b32.most_similar('valdoria', 5)}")
    print(f"PPMI-SVD 32 维：valdoria:valport :: kestry:? → "
          f"{b32.analogy('valdoria', 'valport', 'kestry', 1)}")
    print(f"SGNS loss（dim=32，逐 epoch）首/末：{res['impl'][32]['loss'][0]:.2f} → "
          f"{res['impl'][32]['loss'][-1]:.2f}；训练对 {res['impl'][32]['pairs']} 个")
    sgns, base = res["impl"][32], res["baseline"][32]
    assert sgns["analogy_heldout"] > base["analogy_heldout"], "SGNS 类比应优于 PPMI-SVD"
    assert sgns["analogy_heldout"] > 0.7, "留出类比准确率过低，检查语料/超参"
    assert sgns["purity"] > 0.7, "最近邻纯度过低"
    assert base["purity"] > 0.99 and base["same_side_cos"] > 0.6, "PPMI 基线应呈塌缩形态"


if __name__ == "__main__":
    main()
