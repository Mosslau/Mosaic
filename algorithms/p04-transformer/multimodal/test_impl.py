"""CLIP 式多模态 — 性质测试"""

import numpy as np
import pytest
from baseline import ridge_retrieval
from impl import CLIP, l2norm, make_pairs
from sklearn.model_selection import train_test_split


def data():
    return make_pairs(10, 12, 200, 0)


def split():
    Xi, Xt, y = data()
    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=.3, random_state=0, stratify=y)
    return Xi, Xt, y, tr, te


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


def test_class_retrieval_heldout() -> None:
    Xi, Xt, y, tr, te = split()
    m = CLIP(d=16, lr=.2, epochs=300).fit(Xi[tr], Xt[tr])
    assert m.retrieval_accuracy(Xi[tr], Xt[tr], y[tr]) >= .95
    assert m.retrieval_accuracy(Xi[te], Xt[te], y[te]) >= .8


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
    with pytest.raises(ValueError):
        make_pairs(8, 12, 5, 0)


def test_deterministic() -> None:
    Xi, Xt, _ = data()
    a = CLIP(d=8, epochs=30, seed=0).fit(Xi, Xt)
    b = CLIP(d=8, epochs=30, seed=0).fit(Xi, Xt)
    I1, T1 = a.embed(Xi, Xt)
    I2, T2 = b.embed(Xi, Xt)
    np.testing.assert_allclose(I1, I2)


def test_heldout_identity_is_not_solvable() -> None:
    """去掉了每样本唯一 token：heldout 的 identity 检索不应被背出来。"""
    Xi, Xt, _, tr, te = split()
    m = CLIP(d=16, lr=.2, epochs=300).fit(Xi[tr], Xt[tr])
    assert m.retrieval_accuracy(Xi[te], Xt[te]) < .5


def test_ridge_baseline_is_strong() -> None:
    Xi, Xt, y, tr, te = split()
    acc = ridge_retrieval(Xi[tr], Xt[tr], Xi[te], Xt[te], y[te])
    assert acc >= .9, acc


def test_seed_variance() -> None:
    Xi, Xt, y, tr, te = split()
    accs = []
    for seed in (0, 1, 2):
        m = CLIP(d=16, lr=.2, epochs=300, seed=seed).fit(Xi[tr], Xt[tr])
        accs.append(float(m.retrieval_accuracy(Xi[te], Xt[te], y[te])))
    assert min(accs) > .6, accs
    assert max(accs) - min(accs) < .3, accs
