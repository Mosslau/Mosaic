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
