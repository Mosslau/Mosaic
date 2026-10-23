"""CLIP 式多模态 — 性质测试"""

import numpy as np
import pytest
from impl import CLIP, l2norm, make_pairs


def data():
    return make_pairs(10, 12, 200, 0)


def test_norm() -> None:
    X = np.array([[3.0, 4.0]])
    np.testing.assert_allclose(l2norm(X), [[0.6, 0.8]])


def test_embed_shape() -> None:
    Xi, Xt, y = data()
    m = CLIP(d=8, epochs=10).fit(Xi, Xt)
    img, txt = m.embed(Xi, Xt)
    assert img.shape == (len(Xi), 8) and txt.shape == (len(Xt), 8)


def test_loss_decreases() -> None:
    Xi, Xt, _ = data()
    m = CLIP(d=8, epochs=50).fit(Xi, Xt)
    assert m.loss_history[-1] < m.loss_history[0]


def test_class_retrieval() -> None:
    Xi, Xt, y = data()
    m = CLIP(d=16, lr=.2, epochs=300).fit(Xi, Xt)
    assert m.retrieval_accuracy(Xi, Xt, y) >= .9


def test_similarity_symmetric() -> None:
    Xi, Xt, _ = data()
    m = CLIP(d=8, epochs=20).fit(Xi, Xt)
    S = m.similarity(Xi[:5], Xt[:5])
    assert S.shape == (5, 5)
    np.testing.assert_allclose(S, m.similarity(Xi[:5], Xt[:5]), atol=1e-12)


def test_invalid() -> None:
    with pytest.raises(ValueError):
        CLIP(d=0)
    with pytest.raises(ValueError):
        CLIP(tau=0)
    Xi, Xt, _ = data()
    with pytest.raises(RuntimeError):
        CLIP().embed(Xi, Xt)


def test_deterministic() -> None:
    Xi, Xt, _ = data()
    a = CLIP(d=8, epochs=30, seed=0).fit(Xi, Xt)
    b = CLIP(d=8, epochs=30, seed=0).fit(Xi, Xt)
    I1, T1 = a.embed(Xi, Xt)
    I2, T2 = b.embed(Xi, Xt)
    np.testing.assert_allclose(I1, I2)


def test_identity_retrieval() -> None:
    Xi, Xt, _ = data()
    m = CLIP(d=16, lr=.2, epochs=300).fit(Xi, Xt)
    assert m.retrieval_accuracy(Xi, Xt) > .5
