"""轻量级 CNN — 性质测试（pytest）

覆盖：
- im2col/col2im 与 maxpool 的伴随（转置）性质
- depthwise 与分组卷积等价、形状契约
- 参数量闭式公式（DS 块 / 标准块 / 全模型）
- DS 块有限差分梯度检查（含 BN）
- BN 的 train/eval 边界、初始化边界
- 端到端小数据训练与输入契约
"""

import numpy as np
import pytest
from impl import (
    BatchNorm,
    Conv2D,
    DepthwiseSeparableConv,
    MobileNetLite,
    StandardCNN,
    col2im,
    im2col,
    maxpool_backward,
    maxpool_forward,
)


def tiny_data(n: int = 300, scale: int = 2):
    from sklearn.datasets import load_digits

    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 1, 8, 8)
    X = np.repeat(np.repeat(X, scale, axis=2), scale, axis=3)
    return X[:n], y[:n]


def naive_grouped_conv(X, W, groups, pad):
    """逐样本、逐组、逐位置的参考实现，仅用于小张量对账。"""
    N, C, H, Wd = X.shape
    out_c, cg_in, k, _ = W.shape
    cg_out = out_c // groups
    Xp = np.pad(X, ((0, 0), (0, 0), (pad, pad), (pad, pad)))
    out = np.zeros((N, out_c, H, Wd))
    for n in range(N):
        for g in range(groups):
            for oc in range(cg_out):
                w = W[g * cg_out + oc]
                for i in range(H):
                    for j in range(Wd):
                        win = Xp[n, g * cg_in:(g + 1) * cg_in, i:i + k, j:j + k]
                        out[n, g * cg_out + oc, i, j] = np.sum(win * w)
    return out


def test_im2col_col2im_adjoint() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, 3, 6, 6))
    G = rng.normal(size=im2col(X, 3, pad=1).shape)
    lhs = np.sum(im2col(X, 3, pad=1) * G)
    rhs = np.sum(X * col2im(G, X.shape, 3, pad=1))
    assert abs(lhs - rhs) < 1e-10


def test_maxpool_adjoint() -> None:
    rng = np.random.default_rng(1)
    X = rng.normal(size=(2, 3, 8, 8))
    out, idx = maxpool_forward(X)
    G = rng.normal(size=out.shape)
    assert abs(np.sum(out * G) - np.sum(X * maxpool_backward(G, idx, X.shape))) < 1e-10


def test_depthwise_equals_grouped_conv() -> None:
    """groups=in_channels 的 depthwise 与逐通道手算完全一致。"""
    rng = np.random.default_rng(2)
    X = rng.normal(size=(2, 3, 5, 5))
    c = Conv2D(3, 3, 3, 1, groups=3, rng=np.random.default_rng(3))
    ref = naive_grouped_conv(X, c.W, groups=3, pad=1)
    assert np.abs(c.forward(X) - ref).max() < 1e-10


def test_conv_shapes_and_group_contract() -> None:
    rng = np.random.default_rng(4)
    X = rng.normal(size=(2, 4, 8, 8))
    assert Conv2D(4, 4, 3, 1, groups=4, rng=rng).forward(X).shape == (2, 4, 8, 8)
    assert Conv2D(6, 4, 1, 0, rng=rng).forward(X).shape == (2, 6, 8, 8)
    shrunk = Conv2D(4, 4, 3, 0, rng=rng).forward(X)
    assert shrunk.shape == (2, 4, 6, 6)
    with pytest.raises(ValueError):
        Conv2D(5, 4, groups=3, rng=rng)


def test_param_formula() -> None:
    """DS 块 = 9·Cin + 2·Cin + Cin·Cout + 2·Cout；标准块 = 9·Cin·Cout + 2·Cout。"""
    cin, cout = 8, 16
    ds = DepthwiseSeparableConv(cin, cout, np.random.default_rng(0))
    ds_expected = 9 * cin + 2 * cin + cin * cout + 2 * cout
    assert sum(p.size for p, _ in ds._params) == ds_expected == 248

    std = StandardCNN().init()
    assert sum(p.size for p, _ in std.blocks[0]._params) == 9 * cin * cout + 2 * cout == 1184

    ds_model = MobileNetLite().init()
    widths = ds_model.widths
    formula = 9 * widths[0] + 2 * widths[0]
    for i in range(len(widths) - 1):
        formula += (9 * widths[i] + 2 * widths[i]
                    + widths[i] * widths[i + 1] + 2 * widths[i + 1])
    formula += widths[-1] * 10 + 10
    assert ds_model.n_params() == formula == 2858
    assert std.n_params() == 15554
    assert std.n_params() / ds_model.n_params() > 5.0


def test_forward_shapes_and_gap() -> None:
    X, y = tiny_data(6)
    net = MobileNetLite(random_state=0).init()
    assert net.predict_proba(X).shape == (6, 10)
    np.testing.assert_allclose(net.predict_proba(X).sum(axis=1), 1.0)
    assert net._gap_shape == (6, net.widths[-1], 2, 2)
    assert net._feat.shape == (6, net.widths[-1])
    x = np.maximum(net.stem_bn.forward(net.stem.forward(X), training=False), 0)
    for block in net.blocks:
        x = maxpool_forward(block.forward(x, training=False))[0]
    np.testing.assert_allclose(net._feat, x.mean(axis=(2, 3)))


def test_depthwise_block_gradients() -> None:
    """对 dw/pw 权重与 BN γ 做中心差分，与反向传播的解析梯度对账。"""
    rng = np.random.default_rng(5)
    block = DepthwiseSeparableConv(2, 3, rng)
    X = rng.normal(size=(4, 2, 4, 4))
    G = rng.normal(size=(4, 3, 4, 4))
    block.forward(X, training=True)
    block.backward(G)

    def loss() -> float:
        return float(np.sum(block.forward(X, training=True) * G))

    for arr, grad in ((block.dw.W, block.dw.dW), (block.pw.W, block.pw.dW),
                      (block.dw_bn.gamma, block.dw_bn.dgamma)):
        idx = tuple(int(rng.integers(0, s)) for s in arr.shape)
        old, eps = arr[idx], 1e-5
        arr[idx] = old + eps
        lp = loss()
        arr[idx] = old - eps
        lm = loss()
        arr[idx] = old
        assert abs((lp - lm) / (2 * eps) - grad[idx]) < 1e-6


def test_bn_eval_is_batch_independent() -> None:
    rng = np.random.default_rng(6)
    bn = BatchNorm(3)
    X = rng.normal(size=(8, 3, 4, 4)) + 2.0
    bn.forward(X, training=True)  # 更新一次 running 统计
    running_before = bn.running_mean.copy()

    out_a = bn.forward(X[:3], training=False)
    out_b = bn.forward(np.concatenate([X[:3], X[3:]], axis=0), training=False)[:3]
    np.testing.assert_allclose(out_a, out_b)
    np.testing.assert_allclose(bn.running_mean, running_before)  # eval 不改 running

    train = bn.forward(X, training=True)
    assert not np.allclose(train, bn.forward(X, training=False))


def test_bn_initial_state_and_normalization() -> None:
    rng = np.random.default_rng(7)
    bn = BatchNorm(4)
    X = rng.normal(size=(16, 4, 5, 5))
    out = bn.forward(X, training=False)
    np.testing.assert_allclose(out, X, atol=1e-4)  # 初始 γ=1,β=0,μ=0,σ²=1
    means = bn.forward(X, training=True).transpose(0, 2, 3, 1).reshape(-1, 4).mean(axis=0)
    assert np.abs(means).max() < 1e-10


def test_initialization_boundaries() -> None:
    rng = np.random.default_rng(8)
    dw = Conv2D(32, 32, 3, pad=1, groups=32, rng=rng)
    assert dw.W.shape == (32, 1, 3, 3) and not hasattr(dw, "b")
    assert abs(dw.W.std() - np.sqrt(2.0 / 9)) < 0.05 * np.sqrt(2.0 / 9)
    pw = Conv2D(64, 16, 1, rng=rng)
    assert pw.W.shape == (64, 16, 1, 1)
    assert abs(pw.W.std() - np.sqrt(2.0 / 16)) < 0.05 * np.sqrt(2.0 / 16)
    net = MobileNetLite().init()
    np.testing.assert_allclose(net.head_b, 0.0)
    np.testing.assert_allclose(net.stem_bn.gamma, 1.0)


def test_train_small() -> None:
    X, y = tiny_data(240)
    net = MobileNetLite(lr=0.01, epochs=5, batch_size=32, random_state=0).fit(X, y)
    assert np.mean(net.predict(X) == y) > 0.7
    assert len(net.history["loss"]) == 5 and net.history["loss"][-1] < net.history["loss"][0]


def test_contracts() -> None:
    X, y = tiny_data(20)
    with pytest.raises(ValueError):
        MobileNetLite(widths=(8,))
    with pytest.raises(ValueError):
        MobileNetLite().fit(X[:, 0], y)
    with pytest.raises(ValueError):
        MobileNetLite().fit(X, y[:-1])
    with pytest.raises(ValueError):
        MobileNetLite(n_classes=3).fit(X, y)
    with pytest.raises(RuntimeError):
        MobileNetLite().predict(X)
