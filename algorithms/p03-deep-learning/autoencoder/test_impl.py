"""AutoEncoder — 性质测试（pytest）

覆盖：
- 梯度检查（全参）
- 2D 重构优于 PCA
- denoising 改善加噪重构
- encode/decode 形状
- torch 对照
- 契约
"""

import numpy as np
import pytest
from impl import AutoEncoder
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split


def digits(n_train=600):
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(len(X), -1)
    return train_test_split(X, y, train_size=n_train, random_state=0, stratify=y)


def test_gradient_check() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(4, 8)) ** 2      # 非负，接近 [0,1]
    m = AutoEncoder(latent_dim=2, random_state=0)
    m._init_params(8, np.random.default_rng(1))
    _, cache = m._forward(X)
    grads = m._backward(cache, X, X.size)

    def loss():
        xh, _ = m._forward(X)
        return float(np.mean((xh - X) ** 2))

    worst = 0.0
    eps = 1e-6
    for key, arr in m.params.items():
        for idx in np.ndindex(arr.shape):
            old = arr[idx]
            arr[idx] = old + eps
            lp = loss()
            arr[idx] = old - eps
            lm = loss()
            arr[idx] = old
            worst = max(worst, abs((lp - lm) / (2 * eps) - grads[key][idx]))
    assert worst < 1e-5


def test_2d_beats_pca() -> None:
    X_tr, X_te, _, _ = digits()
    ae = AutoEncoder(latent_dim=2, epochs=100, random_state=0).fit(X_tr)
    pca = PCA(n_components=2).fit(X_tr)
    pe = np.mean((pca.inverse_transform(pca.transform(X_te)) - X_te) ** 2)
    assert ae.reconstruction_error(X_te) < pe


def test_denoising_improves_noisy() -> None:
    X_tr, X_te, _, _ = digits()
    rng = np.random.default_rng(0)
    noisy = np.clip(X_te + rng.normal(0, 0.3, X_te.shape), 0, 1)
    clean = AutoEncoder(latent_dim=8, epochs=100, denoising=0.0, random_state=0).fit(X_tr)
    denoise = AutoEncoder(latent_dim=8, epochs=100, denoising=0.3, random_state=0).fit(X_tr)
    assert denoise.reconstruction_error(noisy) < clean.reconstruction_error(noisy)


def test_shapes() -> None:
    X_tr, X_te, _, _ = digits(200)
    ae = AutoEncoder(latent_dim=4, epochs=5, random_state=0).fit(X_tr)
    assert ae.encode(X_te).shape == (len(X_te), 4)
    assert ae.reconstruct(X_te).shape == X_te.shape
    assert 0 <= ae.reconstruction_error(X_te) <= 1


def test_torch_comparison() -> None:
    pytest.importorskip("torch")
    from framework import TorchAE
    X_tr, X_te, _, _ = digits(400)
    hand = AutoEncoder(latent_dim=8, epochs=30, random_state=0).fit(X_tr)
    torch_ae = TorchAE(latent_dim=8, epochs=30, random_state=0).fit(X_tr)
    assert abs(hand.reconstruction_error(X_te)
               - torch_ae.reconstruction_error(X_te)) < 0.01


def test_invalid_inputs() -> None:
    X_tr, _, _, _ = digits(100)
    with pytest.raises(ValueError):
        AutoEncoder(latent_dim=0)
    with pytest.raises(ValueError):
        AutoEncoder(denoising=-1)
    with pytest.raises(ValueError):
        AutoEncoder().fit(X_tr[:, 0])
    bad = X_tr.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        AutoEncoder().fit(bad)


def test_predict_before_fit() -> None:
    X_tr, _, _, _ = digits(50)
    with pytest.raises(RuntimeError):
        AutoEncoder().encode(X_tr)
