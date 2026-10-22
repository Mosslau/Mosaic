"""RNN 与 LSTM — 性质测试（pytest）

覆盖：
- sigmoid 数值稳定
- RNN / LSTM 的 BPTT 有限差分
- parity 任务上的 LSTM 学习
- h0 梯度随 T 衰减（RNN）
- 梯度裁剪
- 形状/契约
"""

import numpy as np
import pytest
from impl import LSTM, RNN, sigmoid


def parity(n=600, T=8, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(n, T))
    y = X.sum(axis=1) % 2
    return np.eye(2)[X], y


def test_sigmoid_stable() -> None:
    z = np.array([-1000.0, 0.0, 1000.0])
    out = sigmoid(z)
    assert np.isfinite(out).all()
    np.testing.assert_allclose(out, [0.0, 0.5, 1.0], atol=1e-12)


@pytest.mark.parametrize("cls", [RNN, LSTM])
def test_bptt_gradient(cls) -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(3, 4, 2))
    y = np.eye(2)[[0, 1, 0]]
    m = cls(input_size=2, hidden_size=5, n_classes=2, random_state=0)
    m._init_params(np.random.default_rng(1))
    p, c = m.forward(X)
    grads = m.backward(p, y, c)

    def loss():
        pr, _ = m.forward(X)
        return float(-np.mean(np.log(np.clip(pr[np.arange(3), [0, 1, 0]], 1e-12, 1))))

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


def test_lstm_learns_parity() -> None:
    X, y = parity(800, T=8)
    m = LSTM(input_size=2, hidden_size=24, n_classes=2, lr=0.01, epochs=30,
             batch_size=32, clip_norm=1.0, random_state=0).fit(X[:600], y[:600])
    assert np.mean(m.predict(X[600:]) == y[600:]) > 0.9


def test_rnn_h0_gradient_decays() -> None:
    X, y = parity(120, T=4)
    m = RNN(input_size=2, hidden_size=16, n_classes=2, random_state=0)
    m._init_params(np.random.default_rng(0))
    m.classes_ = np.array([0, 1])
    short = m.grad_norm_h0_for_T(X, y)
    Xl, yl = parity(120, T=32, seed=1)
    long = m.grad_norm_h0_for_T(Xl, yl)
    assert long < short


def test_clipping_caps_norm() -> None:
    X, y = parity(400, T=20)
    clipped = RNN(input_size=2, hidden_size=16, n_classes=2, lr=0.5, epochs=3,
                  batch_size=32, clip_norm=1.0, random_state=0).fit(X[:320], y[:320])
    assert max(clipped.grad_norm_history) > 1.0      # 记录的是裁剪前
    assert np.isfinite(clipped.loss_history).all()


def test_variable_length_and_predict_before_fit() -> None:
    X, y = parity(80, T=6)
    m = LSTM(input_size=2, hidden_size=8, n_classes=2, epochs=2, random_state=0).fit(X, y)
    for T in (4, 8, 12):
        X2, _ = parity(20, T=T)
        assert m.predict_proba(X2).shape == (20, 2)
    with pytest.raises(RuntimeError):
        LSTM().predict(X)


def test_invalid_inputs() -> None:
    X, y = parity(40, T=6)
    with pytest.raises(ValueError):
        RNN(input_size=2, n_classes=2).fit(X[:, 0], y)
    with pytest.raises(ValueError):
        RNN(input_size=2, n_classes=2).fit(X, y[:-1])
    with pytest.raises(ValueError):
        RNN(clip_norm=0)
