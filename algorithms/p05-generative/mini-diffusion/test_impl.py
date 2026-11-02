"""DDPM — 性质测试（pytest）"""

import numpy as np
import pytest
from impl import DDPM


def data(n=64, seed=0):
    rng = np.random.default_rng(seed)
    return np.clip(rng.normal(0.4, 0.2, (n, 64)), 0, 1), rng.integers(0, 10, n)


def test_schedule() -> None:
    d = DDPM(n_steps=100)
    assert d.betas.shape == (100,)
    assert np.all(np.diff(d.alphas_bar) < 0)
    assert 0 < d.alphas_bar[-1] < 0.05


def test_q_sample_closed_form() -> None:
    d = DDPM(n_steps=20, random_state=0)
    X = np.full((2, 64), 0.5)
    noise = np.zeros_like(X)
    np.testing.assert_allclose(d.q_sample(X, np.array([0, 0]), noise), X, atol=1e-4)


def test_denoiser_shape() -> None:
    d = DDPM(n_steps=10, hidden=32)
    x = np.zeros((3, 64))
    t = np.array([0, 3, 9])
    y = np.array([0, 1, 9])
    out = d.net.forward(x, t, y, d.n_steps)
    assert out.shape == (3, 64)


def test_train_loss_decreases() -> None:
    X, y = data()
    d = DDPM(n_steps=20, epochs=20, hidden=32)
    losses = d.train(X, y)
    assert losses[-1] < losses[0]


def test_sample_shape() -> None:
    X, y = data()
    d = DDPM(n_steps=20, epochs=20, hidden=32)
    d.train(X, y)
    s = d.sample(5)
    assert s.shape == (5, 64)
    assert s.min() >= 0 and s.max() <= 1


def test_conditional_and_cfg() -> None:
    X, y = data()
    d = DDPM(n_steps=20, epochs=20, hidden=32)
    d.train(X, y)
    labels = np.array([0, 1, 2, 3])
    a = d.sample(4, labels=labels, guidance=0.0, seed=1)
    b = d.sample(4, labels=labels, guidance=3.0, seed=1)
    assert a.shape == b.shape == (4, 64)
    # CFG 不能只是“跑通”：同一 seed 下，w=0 与 w=3 的输出必须不同
    assert not np.allclose(a, b)


def test_sampling_seed_varies() -> None:
    X, y = data()
    d = DDPM(n_steps=20, epochs=20, hidden=32)
    d.train(X, y)
    labels = np.array([0, 1, 2, 3])
    a = d.sample(4, labels=labels, guidance=3.0, seed=1)
    b = d.sample(4, labels=labels, guidance=3.0, seed=2)
    assert not np.allclose(a, b)


@pytest.mark.parametrize("name,idx", [
    ("W1", (0, 0)),
    ("W2", (0, 0)),
    ("W3", (0, 0)),
    ("b3", (0,)),
    ("b2", (0,)),
    ("class_emb", (0, 0)),
])
def test_denoiser_gradients(name, idx) -> None:
    """去噪网络五组参数 + class embedding 的有限差分。"""
    d = DDPM(n_steps=10, hidden=16)
    X, _ = data(8)
    y = np.arange(8) % 10
    t = np.arange(8) % d.n_steps
    out = d.net.forward(X, t, y, d.n_steps)
    dout = np.ones_like(out) / out.size
    d.net.backward(dout)

    def loss():
        return float(d.net.forward(X, t, y, d.n_steps).mean())

    eps = 1e-6
    param = d.net.params()[name]
    analytic = float(d.net.grads()[name][idx])
    old = param[idx]
    param[idx] = old + eps
    lp = loss()
    param[idx] = old - eps
    lm = loss()
    param[idx] = old
    assert abs((lp - lm) / (2 * eps) - analytic) < 1e-4, name


def test_invalid() -> None:
    with pytest.raises(ValueError):
        DDPM(n_steps=1)
    with pytest.raises(ValueError):
        DDPM(n_steps=10, hidden=0)
    d = DDPM(n_steps=10)
    with pytest.raises(ValueError):
        d.sample(0)
    with pytest.raises(ValueError):
        d.sample(2, labels=np.array([10, 11]))
    with pytest.raises(ValueError):
        d.sample(2, labels=np.array([0, 1]), guidance=-1)
