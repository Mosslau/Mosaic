"""推荐系统 — 性质测试"""

import numpy as np
import pytest
from impl import ItemCF, MatrixFactorization, Popularity, make_data, recall_ndcg, train_test_mask


def data():
    R = make_data(30, 20, seed=0)
    tr, te = train_test_mask(R, 0.2, 0)
    return R, tr, te, R * tr


def test_mask_disjoint() -> None:
    R, tr, te, _ = data()
    assert not (tr & te).any()
    assert (tr | te).sum() == (R > 0).sum()


def test_itemcf_recommend_excludes_seen() -> None:
    _, _, _, Rtr = data()
    m = ItemCF(10).fit(Rtr)
    recs = m.recommend(0, 5)
    assert len(recs) == 5
    assert all(Rtr[0, i] == 0 for i in recs)


def test_mf_loss_decreases() -> None:
    _, _, _, Rtr = data()
    m = MatrixFactorization(8, 0.01, 0.05, 10, 0).fit(Rtr)
    assert m.loss_history[-1] < m.loss_history[0]


def test_mf_recommend() -> None:
    _, _, _, Rtr = data()
    m = MatrixFactorization(8, 0.01, 0.05, 10, 0).fit(Rtr)
    assert len(m.recommend(0, 5)) == 5


def test_popularity_order() -> None:
    _, _, _, Rtr = data()
    m = Popularity().fit(Rtr)
    assert len(m.recommend(0, 5)) == 5


def test_recall_range() -> None:
    R, tr, te, Rtr = data()
    m = MatrixFactorization(8, 0.01, 0.05, 10, 0).fit(Rtr)
    rec, ndcg = recall_ndcg(m, R, tr, te, 10)
    assert 0 <= rec <= 1 and 0 <= ndcg <= 1


def test_invalid() -> None:
    with pytest.raises(ValueError):
        MatrixFactorization(n_factors=0)
    with pytest.raises(ValueError):
        ItemCF().fit(np.zeros((0, 5)))
    with pytest.raises(RuntimeError):
        ItemCF().predict(0, 0)
    with pytest.raises(RuntimeError):
        MatrixFactorization().recommend(0)
