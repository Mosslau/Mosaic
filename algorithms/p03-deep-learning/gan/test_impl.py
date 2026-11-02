"""GAN — 性质测试（pytest）

覆盖：
- LeakyReLU
- mode_coverage 指标
- 训练 smoke：损失有限、样本形状
- 生成器/判别器输出域
- 参数确实更新
- 契约
"""

import numpy as np
import pytest
from impl import GAN, _backward, _forward, leaky_relu, mode_coverage


def toy(n=400, seed=0):
    rng = np.random.default_rng(seed)
    centers = np.array([[-2.0, 0.0], [2.0, 0.0], [0.0, -2.0], [0.0, 2.0]])
    X = np.vstack([c + rng.normal(0, 0.1, size=(n // 4, 2)) for c in centers])
    return X, centers


def test_leaky_relu() -> None:
    z = np.array([-1.0, 0.0, 2.0])
    np.testing.assert_allclose(leaky_relu(z), [-0.01, 0.0, 2.0])


def test_mode_coverage() -> None:
    centers = np.array([[0.0, 0.0], [5.0, 5.0]])
    samples = np.array([[0.0, 0.1], [5.1, 5.0], [100.0, 100.0]])
    m = mode_coverage(samples, centers, threshold=0.35)
    assert m["covered"] == 2
    assert m["n_modes"] == 2
    assert m["counts"].tolist() == [1, 1]
    assert m["entropy"] == pytest.approx(np.log(2))


def test_train_smoke() -> None:
    X, _ = toy()
    g = GAN(data_dim=2, latent_dim=8, hidden=(32, 32), lr_g=5e-4, lr_d=5e-5,
            random_state=0).train(X, epochs=30, batch_size=32)
    s = g.sample(64)
    assert s.shape == (64, 2)
    assert np.isfinite(g.d_loss_history).all()
    assert np.isfinite(g.g_loss_history).all()
    assert len(g.d_loss_history) == 30


def test_output_ranges() -> None:
    X, _ = toy()
    g = GAN(data_dim=2, latent_dim=4, hidden=(16,), random_state=0).train(X, epochs=5)
    p = g.discriminator(X)
    assert p.min() >= 0 and p.max() <= 1
    Z = np.random.default_rng(0).normal(size=(10, 4))
    assert g.generator(Z).shape == (10, 2)


def test_sigmoid_output_digits() -> None:
    rng = np.random.default_rng(0)
    X = rng.random((100, 16))          # 假装 4×4 像素
    g = GAN(data_dim=16, latent_dim=4, hidden=(8,), out_sigmoid=True,
            random_state=0).train(X, epochs=5)
    s = g.sample(20)
    assert s.min() >= 0 and s.max() <= 1


def _init_gan():
    g = GAN(data_dim=2, latent_dim=4, hidden=(8,), random_state=0)
    g._init(np.random.default_rng(0))
    return g


def test_discriminator_fd() -> None:
    """判别器 W 的有限差分：BCE(real=1)+BCE(fake=0)。"""
    g = _init_gan()
    rng = np.random.default_rng(0)
    real = rng.normal(size=(6, 2))
    fake = rng.normal(size=(6, 2))

    def loss():
        dr, _ = _forward(g.d_params, real, True)
        df, _ = _forward(g.d_params, fake, True)
        return float(-np.mean(np.log(np.clip(dr, 1e-12, 1)))
                     - np.mean(np.log(np.clip(1 - df, 1e-12, 1))))

    dr, cr = _forward(g.d_params, real, True)
    df, cf = _forward(g.d_params, fake, True)
    dr, df = dr.ravel(), df.ravel()
    # _backward(out_sigmoid=True) 的 dout 语义是 dL/dp，内部再乘 p(1-p) 得 dL/dlogit
    gr, _ = _backward(g.d_params, cr, (-1.0 / (dr * len(real)))[:, None], True)
    gf, _ = _backward(g.d_params, cf,
                      (1.0 / ((1 - df) * len(fake)))[:, None], True)
    analytic = float(gr[0]["W"][0, 0] + gf[0]["W"][0, 0])

    eps = 1e-6
    param = g.d_params[0]["W"]
    old = param[0, 0]
    param[0, 0] = old + eps
    lp = loss()
    param[0, 0] = old - eps
    lm = loss()
    param[0, 0] = old
    assert abs((lp - lm) / (2 * eps) - analytic) < 1e-4


def test_generator_fd() -> None:
    """生成器 W 的有限差分：-log D(G(z))，D 冻结。"""
    g = _init_gan()
    Z = np.random.default_rng(1).normal(size=(6, 4))

    def loss():
        fake, _ = _forward(g.g_params, Z, g.out_sigmoid)
        d, _ = _forward(g.d_params, fake, True)
        return float(-np.mean(np.log(np.clip(d, 1e-12, 1))))

    fake, cg = _forward(g.g_params, Z, g.out_sigmoid)
    d, cd = _forward(g.d_params, fake, True)
    d = d.ravel()
    dlogits = (-1.0 / (np.clip(d, 1e-12, 1) * len(Z)))[:, None]
    _, dfdx = _backward(g.d_params, cd, dlogits, True)
    gradsG, _ = _backward(g.g_params, cg, dfdx, g.out_sigmoid)
    analytic = float(gradsG[0]["W"][0, 0])

    eps = 1e-6
    param = g.g_params[0]["W"]
    old = param[0, 0]
    param[0, 0] = old + eps
    lp = loss()
    param[0, 0] = old - eps
    lm = loss()
    param[0, 0] = old
    assert abs((lp - lm) / (2 * eps) - analytic) < 1e-4


def test_invalid() -> None:
    X, _ = toy()
    with pytest.raises(ValueError):
        GAN(loss_type="wgan")
    with pytest.raises(ValueError):
        GAN().train(X[:, 0], epochs=1)


def test_predict_before_train() -> None:
    with pytest.raises(RuntimeError):
        GAN().sample(2)
