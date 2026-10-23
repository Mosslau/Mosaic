"""GAN 评估协议 — 测试。"""

import numpy as np
import pytest
from evaluate import digit_metrics
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression


def clf():
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    return LogisticRegression(max_iter=2000).fit(X, y)


def test_metrics_keys() -> None:
    c = clf()
    X, _ = load_digits(return_X_y=True)
    m = digit_metrics(X[:100] / 16.0, c)
    assert set(m) >= {"coverage", "entropy", "unique", "nn_distance"}
    assert 0 < m["coverage"] <= 10
    assert 0 <= m["unique"] <= 1


def test_random_low_coverage() -> None:
    c = clf()
    rng = np.random.default_rng(0)
    m = digit_metrics(rng.random((200, 64)), c, min_frac=0.05)
    assert m["coverage"] < 10


def test_invalid() -> None:
    with pytest.raises(ValueError):
        digit_metrics(np.zeros((1, 64)), clf())
    with pytest.raises(ValueError):
        digit_metrics(np.zeros((2, 3)), clf())
