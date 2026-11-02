"""GCN — 性质测试"""

import numpy as np
import pytest
from baseline import mlp_fit_predict
from impl import GCN, make_sbm, normalize_adj


def data():
    A, X, y = make_sbm(30, 0.2, 0.08, 8, seed=0)
    train = np.zeros(len(y), bool)
    for c in (0, 1):
        train[np.where(y == c)[0][:6]] = True
    return A, X, y, train


def test_normalize_symmetric() -> None:
    A = np.array([[0, 1], [1, 0]], dtype=float)
    Ah = normalize_adj(A)
    np.testing.assert_allclose(Ah, Ah.T)
    np.testing.assert_allclose(np.diag(Ah), [0.5, 0.5])


def test_forward_shape() -> None:
    A, X, y, tr = data()
    m = GCN(8, 2, 0.1, 10).fit(A, X, y, tr)
    p = m.predict()
    assert p.shape == (60,)
    assert set(np.unique(p)) <= {0, 1}


def test_loss_decreases() -> None:
    A, X, y, tr = data()
    m = GCN(8, 2, 0.1, 50).fit(A, X, y, tr)
    assert m.loss_history[-1] < m.loss_history[0]


def test_accuracy_beats_mlp() -> None:
    A, X, y, tr = data()
    m = GCN(16, 2, 0.2, 200).fit(A, X, y, tr)
    m._X = X
    pg = m.predict()
    pm = mlp_fit_predict(X, y, tr)
    assert (pg[~tr] == y[~tr]).mean() > 0.75
    assert (pg[~tr] == y[~tr]).mean() >= (pm[~tr] == y[~tr]).mean() - 0.05


@pytest.mark.parametrize("name,idx", [
    ("W1", (0, 0)),
    ("b1", (0,)),
    ("W2", (0, 0)),
    ("b2", (0,)),
])
def test_gcn_gradients(name, idx) -> None:
    """GCN 两层参数（W1/b1/W2/b2）的有限差分。"""
    A, X, y, tr = data()
    m = GCN(8, 2, 0.1, 1).fit(A, X, y, tr)
    _, grads = m._loss_grads(X, y, tr)

    def loss():
        return m._loss_grads(X, y, tr)[0]

    eps = 1e-6
    param = getattr(m, name)
    analytic = float(grads[name][idx])
    old = param[idx]
    param[idx] = old + eps
    lp = loss()
    param[idx] = old - eps
    lm = loss()
    param[idx] = old
    assert abs((lp - lm) / (2 * eps) - analytic) < 1e-4, name


def test_seed_variance() -> None:
    A, X, y, tr = data()
    accs = []
    for seed in (0, 1, 2):
        m = GCN(16, 2, 0.2, 200, seed).fit(A, X, y, tr)
        m._X = X
        accs.append(float((m.predict()[~tr] == y[~tr]).mean()))
    assert min(accs) > 0.7, accs
    assert max(accs) - min(accs) < 0.2, accs


def test_deterministic() -> None:
    A, X, y, tr = data()
    a = GCN(8, 2, 0.1, 30, 0).fit(A, X, y, tr)
    a._X = X
    b = GCN(8, 2, 0.1, 30, 0).fit(A, X, y, tr)
    b._X = X
    np.testing.assert_array_equal(a.predict(), b.predict())


def test_invalid() -> None:
    with pytest.raises(ValueError):
        GCN(hidden=0)
    with pytest.raises(ValueError):
        normalize_adj(np.zeros((2, 3)))
    A, X, y, _ = data()
    with pytest.raises(ValueError):
        GCN().fit(A, X, y, np.zeros(60, bool))
    with pytest.raises(RuntimeError):
        GCN().predict()


def test_fit_predict() -> None:
    A, X, y, tr = data()
    m = GCN(8, 2, 0.1, 30)
    p = m.fit_predict(A, X, y, tr)
    assert p.shape == (60,)


def test_no_self_loops() -> None:
    A, X, y, tr = data()
    Ah = normalize_adj(A)
    assert np.all(np.diag(Ah) > 0)
