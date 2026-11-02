"""文本主题模型 — 性质测试"""

import numpy as np
import pytest
from demo import make_docs
from impl import NMF, Tfidf


def data():
    docs, labels, names = make_docs()
    tf = Tfidf().fit(docs)
    return docs, labels, names, tf, tf.transform(docs)


def test_tfidf_shape_norm() -> None:
    *_, tf, X = data()
    assert X.shape == (24, len(tf.vocab))
    np.testing.assert_allclose(np.linalg.norm(X, axis=1), 1.0, atol=1e-6)


def test_loss_decreases() -> None:
    *_, X = data()
    m = NMF(3, 100, 0).fit(X)
    assert m.loss_history[-1] < m.loss_history[0]


def test_topics_recover() -> None:
    *_, tf, X = data()
    m = NMF(3, 200, 0).fit(X)
    flat = {w for words in m.top_words(tf.vocab, 5) for w in words}
    assert {"rocket", "pizza", "tennis"} & flat
    assert len(m.top_words(tf.vocab, 5)) == 3


def test_transform_shape() -> None:
    *_, X = data()
    m = NMF(3, 50, 0).fit(X)
    W = m.transform(X)
    assert W.shape == (24, 3)
    assert (W >= 0).all()


def test_cluster_purity() -> None:
    docs, labels, _, _, X = data()
    m = NMF(3, 200, 0).fit(X)
    pred = m.transform(X).argmax(1)
    labels = np.asarray(labels)
    mapping = {k: int(np.bincount(labels[pred == k], minlength=3).argmax())
               for k in range(3)}
    assert np.mean([mapping[p] == y for p, y in zip(pred, labels)]) >= 0.9


def test_invalid() -> None:
    with pytest.raises(ValueError):
        NMF(0)
    with pytest.raises(ValueError):
        NMF(3).fit(np.array([[1.0, -1.0]]))
    with pytest.raises(RuntimeError):
        NMF().transform(np.zeros((1, 3)))


def test_deterministic() -> None:
    *_, X = data()
    a = NMF(3, 50, 0).fit(X)
    b = NMF(3, 50, 0).fit(X)
    np.testing.assert_allclose(a.W, b.W)


def test_top_words_contract() -> None:
    *_, tf, X = data()
    m = NMF(3, 30, 0).fit(X)
    words = m.top_words(tf.vocab, 4)
    assert all(len(w) == 4 for w in words)


def test_sklearn_baseline() -> None:
    import framework
    *_, X = data()
    m = framework.fit_nmf(X, 3)
    assert m.reconstruction_err_ < 4.0


def test_lda_baseline() -> None:
    """不同模型族的公平基线：LDA 同 TF-IDF、同主题数。"""
    import framework
    *_, X = data()
    m = framework.fit_lda(X, 3)
    W = m.transform(X)
    assert W.shape == (24, 3)
    assert np.isfinite(m.perplexity(X))


def test_heldout_purity() -> None:
    """在 18/6 的 heldout 文档上评估主题纯度，而不是只在训练集上聚类。"""
    from sklearn.model_selection import train_test_split

    docs, labels, _ = make_docs()
    labels = np.asarray(labels)
    idx = np.arange(len(docs))
    tr, te = train_test_split(idx, test_size=6, random_state=0, stratify=labels)
    tf = Tfidf().fit([docs[i] for i in tr])
    Xtr, Xte = tf.transform([docs[i] for i in tr]), tf.transform([docs[i] for i in te])
    m = NMF(3, 200, 0).fit(Xtr)
    pred_tr = m.transform(Xtr).argmax(1)
    mapping = {k: int(np.bincount(labels[tr][pred_tr == k], minlength=3).argmax())
               for k in range(3)}
    pred_te = m.transform(Xte).argmax(1)
    purity = float(np.mean([mapping[p] == y for p, y in zip(pred_te, labels[te])]))
    assert purity >= 0.8, purity
