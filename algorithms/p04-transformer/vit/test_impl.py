"""ViT-lite — 性质测试"""

import numpy as np
import pytest
from impl import ViT
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split


def data():
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 1, 8, 8)
    return train_test_split(X, y, test_size=.2, random_state=0, stratify=y)


def test_forward_shape() -> None:
    Xtr, _, ytr, _ = data()
    m = ViT(d=8, epochs=2).fit(Xtr[:100], ytr[:100])
    p = m.predict_proba(Xtr[:7])
    assert p.shape == (7, 10)
    np.testing.assert_allclose(p.sum(1), 1.0)


def test_loss_decreases() -> None:
    Xtr, _, ytr, _ = data()
    m = ViT(d=32, lr=.1, epochs=20).fit(Xtr, ytr)
    assert m.loss_history[-1] < m.loss_history[0]


def test_accuracy() -> None:
    Xtr, Xte, ytr, yte = data()
    m = ViT(d=64, lr=.1, epochs=200, seed=0).fit(Xtr, ytr)
    assert (m.predict(Xte) == yte).mean() > .75


def test_patch_count() -> None:
    Xtr, _, ytr, _ = data()
    m = ViT(d=8, epochs=1).fit(Xtr[:50], ytr[:50])
    assert m.patches.shape[1:] == (4, 16)


def test_invalid() -> None:
    with pytest.raises(ValueError):
        ViT(d=0)
    with pytest.raises(ValueError):
        ViT().fit(np.zeros((2, 1, 8, 7)), np.array([0, 1]))
    with pytest.raises(RuntimeError):
        ViT().predict(np.zeros((2, 1, 8, 8)))


def test_deterministic() -> None:
    Xtr, _, ytr, _ = data()
    a = ViT(d=8, epochs=5, seed=0).fit(Xtr[:100], ytr[:100])
    b = ViT(d=8, epochs=5, seed=0).fit(Xtr[:100], ytr[:100])
    np.testing.assert_allclose(a.predict_proba(Xtr[:5]), b.predict_proba(Xtr[:5]))


def test_n_classes() -> None:
    Xtr, _, ytr, _ = data()
    mask = ytr < 3
    m = ViT(d=8, n_classes=3, epochs=5).fit(Xtr[mask][:60], ytr[mask][:60])
    assert m.predict_proba(Xtr[:4]).shape[1] == 3


def test_reproducible() -> None:
    Xtr, _, ytr, _ = data()
    m = ViT(d=16, epochs=3, seed=0).fit(Xtr[:80], ytr[:80])
    assert np.isfinite(m.loss_history).all()
