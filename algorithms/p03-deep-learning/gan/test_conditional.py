"""条件 GAN — 测试。"""

import numpy as np
import pytest
from conditional import ConditionalGAN
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split


def data():
    X, y = load_digits(return_X_y=True)
    X = (X / 16).reshape(len(X), -1)
    return train_test_split(X, y, train_size=800, random_state=0, stratify=y)


def test_sample_shape() -> None:
    Xtr, _, ytr, _ = data()
    c = ConditionalGAN(epochs=5).train(Xtr, ytr)
    s = c.sample(20, labels=np.arange(10).repeat(2))
    assert s.shape == (20, 64)
    assert s.min() >= 0 and s.max() <= 1


def test_class_condition() -> None:
    Xtr, Xte, ytr, yte = data()
    clf = LogisticRegression(max_iter=3000).fit(Xtr, ytr)
    c = ConditionalGAN().train(Xtr, ytr)
    labels = np.tile(np.arange(10), 26)[:260]
    s = c.sample(260, labels=labels)
    counts = np.bincount(clf.predict(s), minlength=10)
    assert np.sum(counts > 0) >= 8


def test_invalid() -> None:
    with pytest.raises(ValueError):
        ConditionalGAN().train(np.zeros((2, 3)), np.array([0, 1]))
    with pytest.raises(RuntimeError):
        ConditionalGAN().sample(2)
