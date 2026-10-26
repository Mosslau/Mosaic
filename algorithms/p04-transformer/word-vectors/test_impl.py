"""词向量：SGNS — 性质测试（11 个）。"""

import numpy as np
import pytest

from baseline import PPMISVD, build_cooc, ppmi
from demo import analogy_items, build_corpus
from impl import SkipGramNS, build_vocab, l2_normalize, noise_cdf, subsample_keep

TINY = [["a", "b"]] * 60 + [["c", "d"]] * 60 + [["e", "f"]] * 60


def tiny_model(dim=8, epochs=30, **kw):
    # 小语料总词数少，子采样阈值必须关掉，否则大部分 token 会被丢掉
    return SkipGramNS(dim=dim, epochs=epochs, lr=2.0, negative=5, subsample=1.0,
                      seed=0, **kw).fit(TINY)


def test_vocab_min_count_and_order():
    vocab, w2i, counts = build_vocab([["a", "a", "b"], ["c", "a"]])
    assert vocab == ["a", "b", "c"] and w2i["a"] == 0        # 词频降序、同频按字典序
    np.testing.assert_array_equal(counts, [3, 1, 1])
    assert build_vocab([["a", "a", "b", "b", "c"]], min_count=2)[0] == ["a", "b"]
    with pytest.raises(ValueError):
        build_vocab([["a", "b"]], min_count=2)               # 过滤后不足 2 个词


def test_noise_distribution_is_power_law():
    counts = np.array([1000.0, 100.0, 10.0, 1.0])
    cdf = noise_cdf(counts, power=0.75)
    assert cdf[-1] == pytest.approx(1.0) and np.all(np.diff(cdf) > 0)
    rng = np.random.default_rng(0)
    draw = np.minimum(np.searchsorted(cdf, rng.random(40000)), 3)
    emp = np.bincount(draw, minlength=4) / 40000
    want = counts ** 0.75 / (counts ** 0.75).sum()
    assert np.abs(emp - want).max() < 0.02                   # 采样频率≈count^0.75


def test_subsample_keep_monotone():
    keep = subsample_keep(np.array([1000.0, 100.0, 2.0]), 1102.0, 1e-2)
    assert np.all((keep >= 0) & (keep <= 1))
    assert keep[0] < keep[1] < keep[2] == 1.0                # 越高频越容易被丢


def test_vectors_shape_and_unit_norm():
    m = tiny_model(dim=8)
    assert m.vectors.shape == (6, 8) and m.W_in.shape == m.W_out.shape == (6, 8)
    np.testing.assert_allclose(np.linalg.norm(m.vectors, axis=1), 1.0, atol=1e-9)
    np.testing.assert_allclose(m.vectors, l2_normalize(m.W_in + m.W_out), atol=1e-9)


def test_pairs_respect_sentence_boundary():
    m = SkipGramNS(dim=4, window=1, negative=0, epochs=1, subsample=1.0,
                   seed=0).fit([["a", "b"], ["c", "d"]])
    assert m.n_pairs == 4                                    # 每句内两个方向，不跨句
    m2 = SkipGramNS(dim=4, window=3, negative=0, epochs=1, subsample=1.0,
                    seed=0).fit([["a"], ["b"]])
    assert m2.n_pairs == 0                                   # 单 token 句子没有上下文对


def test_cooccurring_words_are_close():
    m = tiny_model()
    assert m.most_similar("a", 1)[0][0] == "b"
    assert m.similarity("a", "b") > m.similarity("a", "c")
    assert m.loss_history[-1] < m.loss_history[0]            # 训练确实在降损


def test_deterministic_with_same_seed():
    a = SkipGramNS(dim=8, epochs=3, seed=0).fit(TINY)
    b = SkipGramNS(dim=8, epochs=3, seed=0).fit(TINY)
    c = SkipGramNS(dim=8, epochs=3, seed=1).fit(TINY)
    np.testing.assert_array_equal(a.vectors, b.vectors)
    assert not np.allclose(a.vectors, c.vectors)


def test_most_similar_contract():
    m = tiny_model()
    out = m.most_similar("a", 3)
    assert len(out) == 3 and "a" not in [w for w, _ in out]
    scores = [s for _, s in out]
    assert scores == sorted(scores, reverse=True)
    with pytest.raises(KeyError):
        m.most_similar("不存在")


def test_analogy_excludes_query_words():
    m = tiny_model()
    out = m.analogy("a", "b", "c", topk=3)
    assert len(out) == 3
    assert not {"a", "b", "c"} & {w for w, _ in out}
    with pytest.raises(KeyError):
        m.analogy("a", "b", "不存在")


def test_invalid_params_and_empty_corpus():
    for kw in ({"dim": 0}, {"window": 0}, {"negative": -1}, {"lr": 0},
               {"epochs": 0}, {"min_count": 0}, {"batch": 0}, {"subsample": 1.5},
               {"noise_power": -1}):
        with pytest.raises(ValueError):
            SkipGramNS(**kw)
    with pytest.raises(ValueError):
        SkipGramNS().fit([])
    with pytest.raises(ValueError):
        SkipGramNS().fit([[], []])


def test_ppmi_baseline_contract():
    sents = [["a", "b"]] * 5 + [["b", "c"]] * 5
    _, w2i, _ = build_vocab(sents)
    C = build_cooc(sents, w2i, window=1)
    np.testing.assert_allclose(C, C.T)                       # 对称窗口的共现矩阵对称
    M = ppmi(C)
    assert M.min() >= 0 and M.shape == C.shape               # PPMI 只保留正相关
    b = PPMISVD(dim=2, window=1, seed=0).fit(sents)
    assert b.vectors.shape == (3, 2) and sorted(b.word2id) == ["a", "b", "c"]
    np.testing.assert_allclose(np.linalg.norm(b.vectors, axis=1), 1.0, atol=1e-9)


def test_full_corpus_quality():
    """整份合成语料上跑一遍：留出类比要明显高于随机（随机≈1/91）。"""
    sentences, meta = build_corpus(0)
    m = SkipGramNS(dim=16, epochs=40, seed=0).fit(sentences)
    items = [it for it in analogy_items() if it["split"] == "heldout"]
    from demo import analogy_top1
    assert analogy_top1(m.vectors, m.word2id, items) > 0.7
    assert meta["vocab"] == len(m.vocab)
