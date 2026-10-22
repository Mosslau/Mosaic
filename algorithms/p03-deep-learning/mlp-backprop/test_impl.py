"""MLP 与手写反向传播 — 性质测试（pytest）

覆盖：
- ReLU / softmax 数值性质
- 有限差分梯度检查（整网）
- digits 子集上训练精度
- 零初始化对称性失败、He 初始化有效
- 优化器、dropout、LR schedule、early stopping
- torch 对照（缺 torch 时跳过）
- 契约
"""

import numpy as np
import pytest
from impl import MLP, relu, relu_grad, softmax
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split


def digits(n=900, seed=0):
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    return train_test_split(X, y, train_size=n, random_state=seed, stratify=y)


def test_relu_softmax() -> None:
    z = np.array([[-1.0, 0.0, 2.0]])
    np.testing.assert_allclose(relu(z), [[0.0, 0.0, 2.0]])
    np.testing.assert_allclose(relu_grad(z), [[0.0, 0.0, 1.0]])
    p = softmax(np.array([[1000.0, 1001.0, 1002.0]]))
    assert np.isfinite(p).all()
    np.testing.assert_allclose(p.sum(axis=1), 1.0)
    assert p[0, 2] > p[0, 1] > p[0, 0]


def test_gradient_check() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(4, 3))
    y = np.eye(3)[[0, 1, 2, 0]]
    m = MLP(hidden_sizes=(4,), init="random", weight_decay=0.0, random_state=0)
    m._init_params(3, 3)
    _, cache = m.forward(X)
    grads = m.backward(cache, y)
    eps = 1e-6
    for layer in range(len(m.params)):
        for key in ("W", "b"):
            arr = m.params[layer][key]
            for idx in np.ndindex(arr.shape):
                old = arr[idx]
                arr[idx] = old + eps
                plus = m._loss(X, y)
                arr[idx] = old - eps
                minus = m._loss(X, y)
                arr[idx] = old
                num = (plus - minus) / (2 * eps)
                assert abs(num - grads[layer][key][idx]) < 1e-5


def test_digits_training() -> None:
    X_tr, X_te, y_tr, y_te = digits()
    m = MLP(hidden_sizes=(64, 32), lr=0.01, epochs=20, batch_size=32,
            optimizer="adam", init="he", random_state=0).fit(X_tr, y_tr)
    assert np.mean(m.predict(X_te) == y_te) > 0.9
    assert len(m.loss_history) == m.epochs_run


def test_zero_init_fails() -> None:
    X_tr, X_te, y_tr, y_te = digits()
    m = MLP(hidden_sizes=(64, 32), lr=0.01, epochs=10, optimizer="adam",
            init="zero", random_state=0).fit(X_tr, y_tr)
    assert np.mean(m.predict(X_te) == y_te) < 0.2


def test_optimizers_train() -> None:
    X_tr, X_te, y_tr, y_te = digits()
    for opt in ("sgd", "momentum", "adam"):
        lr = 0.05 if opt == "sgd" else 0.01
        m = MLP(hidden_sizes=(32,), lr=lr, epochs=10, optimizer=opt,
                init="he", random_state=0).fit(X_tr, y_tr)
        assert np.mean(m.predict(X_te) == y_te) > 0.85


def test_dropout_probability_normalized() -> None:
    X_tr, X_te, y_tr, _ = digits()
    m = MLP(hidden_sizes=(32,), lr=0.01, epochs=5, optimizer="adam",
            dropout=0.3, random_state=0).fit(X_tr, y_tr)
    p = m.predict_proba(X_te)
    np.testing.assert_allclose(p.sum(axis=1), 1.0)
    np.testing.assert_allclose(p, m.predict_proba(X_te))   # eval 无随机性


def test_lr_schedule_and_early_stopping() -> None:
    X_tr, X_te, y_tr, y_te = digits()
    m = MLP(hidden_sizes=(32,), lr=0.02, epochs=10, optimizer="adam",
            lr_schedule="cosine", random_state=0).fit(X_tr, y_tr)
    assert m.current_lr_ < 0.02

    X_tr2, X_te2, y_tr2, y_te2 = digits()
    e = MLP(hidden_sizes=(32,), lr=0.01, epochs=50, optimizer="adam",
            early_stopping=True, patience=2, validation_split=0.2,
            random_state=0).fit(X_tr2, y_tr2)
    assert e.epochs_run < 50
    assert np.mean(e.predict(X_te2) == y_te2) > 0.85


def test_torch_comparison() -> None:
    pytest.importorskip("torch")
    from framework import fit_torch_mlp
    X_tr, X_te, y_tr, y_te = digits()
    hand = MLP(hidden_sizes=(32,), lr=0.01, epochs=10, optimizer="adam",
               init="he", random_state=0).fit(X_tr, y_tr)
    torch_model = fit_torch_mlp(X_tr, y_tr, hidden_sizes=(32,), lr=0.01, epochs=10,
                                optimizer="adam", init="he", random_state=0)
    a = np.mean(hand.predict(X_te) == y_te)
    b = np.mean(torch_model.predict(X_te) == y_te)
    assert abs(a - b) < 0.05


def test_invalid_inputs() -> None:
    X_tr, _, y_tr, _ = digits()
    with pytest.raises(ValueError):
        MLP(hidden_sizes=())
    with pytest.raises(ValueError):
        MLP(optimizer="rmsprop")
    with pytest.raises(ValueError):
        MLP(init="magic")
    with pytest.raises(ValueError):
        MLP(dropout=1.0)
    with pytest.raises(ValueError):
        MLP().fit(X_tr[:, 0], y_tr)
    with pytest.raises(ValueError):
        MLP().fit(X_tr, y_tr[:-1])
    bad = X_tr.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        MLP().fit(bad, y_tr)


def test_predict_before_fit() -> None:
    X_tr, _, _, _ = digits()
    with pytest.raises(RuntimeError):
        MLP().predict(X_tr)
