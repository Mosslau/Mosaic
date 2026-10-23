"""VAE — 性质测试（pytest）

覆盖：
- encode 双头、重参数化
- KL 公式（非负/零点）、ELBO 训练
- 重构/采样/插值
- 与均值基线对照
- 契约
"""

import numpy as np
import pytest
from impl import VAE


def data(n=128, seed=0):
    rng = np.random.default_rng(seed)
    return np.clip(rng.normal(0.4, 0.2, (n, 64)), 0, 1)


def test_encode_shapes() -> None:
    X = data()
    v = VAE(latent_dim=2)
    mu, lv = v.encode(X)
    assert mu.shape == (len(X), 2)
    assert lv.shape == (len(X), 2)


def test_reparameterize() -> None:
    v = VAE(latent_dim=2)
    mu = np.zeros((3, 2))
    lv = np.zeros((3, 2))
    z1 = v.reparameterize(mu, lv, np.random.default_rng(0))
    z2 = v.reparameterize(mu, lv, np.random.default_rng(0))
    np.testing.assert_allclose(z1, z2)
    assert z1.shape == (3, 2)


def test_kl_zero_and_nonnegative() -> None:
    mu = np.zeros((4, 2))
    lv = np.zeros((4, 2))
    kl0 = float(np.mean(-0.5 * np.sum(1 + lv - mu ** 2 - np.exp(lv), axis=1)))
    assert abs(kl0) < 1e-12
    rng = np.random.default_rng(0)
    mu, lv = rng.normal(size=(4, 2)), rng.normal(size=(4, 2))
    kl = -0.5 * (1 + lv - mu ** 2 - np.exp(lv))
    assert np.all(kl >= 0)


def test_fit_loss_decreases() -> None:
    X = data()
    v = VAE(latent_dim=2, epochs=20, random_state=0)
    v.fit(X)
    assert v.loss_history[-1] < v.loss_history[0]


def test_reconstruct_and_sample() -> None:
    X = data()
    v = VAE(latent_dim=2, epochs=20, random_state=0).fit(X)
    R = v.reconstruct(X)
    S = v.sample(8)
    assert R.shape == X.shape
    assert S.shape == (8, 64)
    assert S.min() >= 0 and S.max() <= 1


def test_reconstruction_beats_mean() -> None:
    from sklearn.datasets import load_digits
    X = load_digits(return_X_y=True)[0][:600] / 16.0
    v = VAE(latent_dim=2, beta=0.1, epochs=80, random_state=0).fit(X)
    mse = np.mean((v.reconstruct(X) - X) ** 2)
    mean_mse = np.mean((X.mean(0) - X) ** 2)
    assert mse < mean_mse


def test_interpolate() -> None:
    v = VAE(latent_dim=2, epochs=5, random_state=0)
    out = v.interpolate(np.array([0.0, 0.0]), np.array([1.0, 1.0]), 5)
    assert out.shape == (5, 64)


def test_kl_gradient_formula() -> None:
    rng = np.random.default_rng(0)
    mu = rng.normal(size=(3, 2))
    lv = rng.normal(size=(3, 2))
    eps = 1e-6
    for idx in [(0, 0), (1, 1)]:
        old = mu[idx]
        mu[idx] = old + eps
        kp = np.mean(-0.5 * np.sum(1 + lv - mu ** 2 - np.exp(lv), axis=1))
        mu[idx] = old - eps
        km = np.mean(-0.5 * np.sum(1 + lv - mu ** 2 - np.exp(lv), axis=1))
        mu[idx] = old
        assert abs((kp - km) / (2 * eps) - (mu[idx] / len(mu))) < 1e-8


def test_invalid() -> None:
    with pytest.raises(ValueError):
        VAE(latent_dim=0)
    with pytest.raises(ValueError):
        VAE(hidden=0)
    with pytest.raises(ValueError):
        VAE(beta=-1)
    v = VAE()
    with pytest.raises(ValueError):
        v.fit(np.zeros((3, 10)))
    with pytest.raises(ValueError):
        v.fit(np.zeros((0, 64)))
    with pytest.raises(ValueError):
        v.sample(0)
    with pytest.raises(ValueError):
        v.decode(np.zeros((2, 3)))
    with pytest.raises(ValueError):
        v.interpolate(np.zeros(2), np.zeros(3), 5)
