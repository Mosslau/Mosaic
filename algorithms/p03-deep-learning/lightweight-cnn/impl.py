"""轻量级 CNN：深度可分离卷积 — 手写实现（深度模型 · 判别式）

numpy 手写 depthwise 3×3（groups=in_channels）+ pointwise 1×1、BatchNorm、
2×2 池化、GAP 与全套反向；stride 固定 1，下采样靠池化。默认 16×16 输入
（digits 8×8 最近邻上采样）：
    stem(1→8) → DS(8→16) → DS(16→32) → DS(32→32) → GAP → 线性头(32→10)

    net = MobileNetLite(widths=(8,16,32,32)).fit(X, y)   # X: (N,1,16,16)
    net.n_params(); net.predict(X)

`StandardCNN` 通道数/池化/线性头相同，只把 DS 块换成标准 3×3 卷积做对照。
卷积不带 bias（BN 的 β 承担偏移）；手写纪律：反向自己写，torch 只在 framework.py。
"""

from __future__ import annotations

import numpy as np


def im2col(X: np.ndarray, k: int, pad: int = 0) -> np.ndarray:
    """(N,C,H,W) → (N*out_h*out_w, C*k*k)，重叠窗口重复取。"""
    if pad:
        X = np.pad(X, ((0, 0), (0, 0), (pad, pad), (pad, pad)))
    N, C, H, W = X.shape
    v = np.lib.stride_tricks.sliding_window_view(X, (k, k), axis=(2, 3))
    return v.transpose(0, 2, 3, 1, 4, 5).reshape(N * (H - k + 1) * (W - k + 1), C * k * k)


def col2im(dcols: np.ndarray, shape: tuple, k: int, pad: int = 0) -> np.ndarray:
    """im2col 的转置：重叠窗口的梯度**累加**回原图。"""
    N, C, H, W = shape
    oh, ow = H + 2 * pad - k + 1, W + 2 * pad - k + 1
    d = dcols.reshape(N, oh, ow, C, k, k).transpose(0, 3, 1, 2, 4, 5)
    dX = np.zeros((N, C, H + 2 * pad, W + 2 * pad), dtype=dcols.dtype)
    for i in range(k):
        for j in range(k):
            dX[:, :, i:i + oh, j:j + ow] += d[..., i, j]
    return dX[:, :, pad:pad + H, pad:pad + W] if pad else dX


def maxpool_forward(X: np.ndarray):
    """2×2 stride-2 最大池化；返回 (输出, argmax 索引)。"""
    N, C, H, W = X.shape
    if H % 2 or W % 2:
        raise ValueError("2×2 池化要求偶数尺寸")
    x = X.reshape(N, C, H // 2, 2, W // 2, 2).transpose(0, 1, 2, 4, 3, 5).reshape(
        N, C, H // 2, W // 2, 4)
    idx = x.argmax(axis=-1)
    return np.take_along_axis(x, idx[..., None], axis=-1)[..., 0], idx


def maxpool_backward(dout: np.ndarray, idx: np.ndarray, shape: tuple) -> np.ndarray:
    """梯度只回传给前向最大值的那个位置。"""
    N, C, H, W = shape
    d = np.zeros((N, C, H // 2, W // 2, 4))
    np.put_along_axis(d, idx[..., None], dout[..., None], axis=-1)
    return d.reshape(N, C, H // 2, W // 2, 2, 2).transpose(0, 1, 2, 4, 3, 5).reshape(N, C, H, W)


def relu(z):
    return np.maximum(0.0, z)


def relu_grad(z):
    return (z > 0).astype(float)


def softmax(z):
    e = np.exp(z - z.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


class BatchNorm:
    """逐通道 BN：训练用 batch 统计并更新 running，推理用 running。"""

    def __init__(self, channels: int, momentum: float = 0.9, eps: float = 1e-5) -> None:
        self.gamma, self.beta = np.ones(channels), np.zeros(channels)
        self.dgamma, self.dbeta = np.zeros(channels), np.zeros(channels)
        self.running_mean, self.running_var = np.zeros(channels), np.ones(channels)
        self.momentum, self.eps = momentum, eps
        self._params = [(self.gamma, self.dgamma), (self.beta, self.dbeta)]

    def forward(self, X, training: bool):
        N, C, H, W = X.shape
        x = X.transpose(0, 2, 3, 1).reshape(-1, C)
        if training:
            mean, var = x.mean(axis=0), x.var(axis=0)
            self.running_mean = self.momentum * self.running_mean + (1 - self.momentum) * mean
            self.running_var = self.momentum * self.running_var + (1 - self.momentum) * var
        else:
            mean, var = self.running_mean, self.running_var
        std = np.sqrt(var + self.eps)
        xhat = (x - mean) / std
        self.cache = (xhat, std, X.shape)
        return (self.gamma * xhat + self.beta).reshape(N, H, W, C).transpose(0, 3, 1, 2)

    def backward(self, dout):
        xhat, std, (N, C, H, W) = self.cache
        dy = dout.transpose(0, 2, 3, 1).reshape(-1, C)
        self.dgamma[...], self.dbeta[...] = (dy * xhat).sum(axis=0), dy.sum(axis=0)
        dxhat = dy * self.gamma
        # batch 均值/方差也依赖输入，故再减去两项（完整 BN 反传）
        dx = (dxhat - dxhat.mean(0) - xhat * (dxhat * xhat).mean(0)) / std
        return dx.reshape(N, H, W, C).transpose(0, 3, 1, 2)


class Conv2D:
    """分组卷积：groups=1 标准卷积；groups=in_channels=out_channels 时即 depthwise。"""

    def __init__(self, out_channels: int, in_channels: int, k: int = 3, pad: int = 0,
                 groups: int = 1, rng=None) -> None:
        if in_channels % groups or out_channels % groups:
            raise ValueError("in/out channels 必须能被 groups 整除")
        rng = rng or np.random.default_rng(0)
        self.W = rng.normal(0.0, np.sqrt(2.0 / ((in_channels // groups) * k * k)),
                            size=(out_channels, in_channels // groups, k, k))
        self.dW = np.zeros_like(self.W)
        self.k, self.pad, self.groups = k, pad, groups
        self._params = [(self.W, self.dW)]

    def forward(self, X):
        N, C, H, W = self.X_shape = X.shape
        self.cols = im2col(X, self.k, self.pad)
        oh, ow = H + 2 * self.pad - self.k + 1, W + 2 * self.pad - self.k + 1
        cg_out = self.W.shape[0] // self.groups
        cols = self.cols.reshape(-1, self.groups, C // self.groups * self.k * self.k)
        Wg = self.W.reshape(self.groups, cg_out, -1)
        # 分组卷积：每组独立矩阵乘（einsum 的 g 维不求和）
        return np.einsum("ngi,goi->ngo", cols, Wg).reshape(
            N, oh, ow, -1).transpose(0, 3, 1, 2)

    def backward(self, dout):
        N, C, H, W = self.X_shape
        d2 = dout.transpose(0, 2, 3, 1).reshape(-1, self.W.shape[0])
        cg_out = self.W.shape[0] // self.groups
        d2g = d2.reshape(-1, self.groups, cg_out)
        cols = self.cols.reshape(-1, self.groups, C // self.groups * self.k * self.k)
        Wg = self.W.reshape(self.groups, cg_out, -1)
        self.dW[...] = np.einsum("ngo,ngi->goi", d2g, cols).reshape(self.W.shape)
        dcols = np.einsum("ngo,goi->ngi", d2g, Wg).reshape(-1, C * self.k * self.k)
        return col2im(dcols, self.X_shape, self.k, self.pad)


class DepthwiseSeparableConv:
    """depthwise 3×3（每通道一个核）→ BN → ReLU → pointwise 1×1 → BN → ReLU。"""

    def __init__(self, in_ch: int, out_ch: int, rng=None) -> None:
        self.dw = Conv2D(in_ch, in_ch, 3, 1, groups=in_ch, rng=rng)
        self.dw_bn = BatchNorm(in_ch)
        self.pw = Conv2D(out_ch, in_ch, 1, 0, rng=rng)
        self.pw_bn = BatchNorm(out_ch)
        self._params = (self.dw._params + self.dw_bn._params
                        + self.pw._params + self.pw_bn._params)

    def forward(self, X, training: bool):
        self.z1 = self.dw_bn.forward(self.dw.forward(X), training)
        self.z2 = self.pw_bn.forward(self.pw.forward(relu(self.z1)), training)
        return relu(self.z2)

    def backward(self, d):
        d = self.pw_bn.backward(d * relu_grad(self.z2))
        d = self.dw_bn.backward(self.pw.backward(d) * relu_grad(self.z1))
        return self.dw.backward(d)


class StandardBlock:
    """标准 3×3 卷积块：Conv(Cin→Cout) → BN → ReLU。"""

    def __init__(self, in_ch: int, out_ch: int, rng=None) -> None:
        self.conv = Conv2D(out_ch, in_ch, 3, 1, rng=rng)
        self.bn = BatchNorm(out_ch)
        self._params = self.conv._params + self.bn._params

    def forward(self, X, training: bool):
        self.z = self.bn.forward(self.conv.forward(X), training)
        return relu(self.z)

    def backward(self, d):
        return self.conv.backward(self.bn.backward(d * relu_grad(self.z)))


class _ConvNet:
    """公共训练循环；子类只换 Block（Adam 也手写）。"""
    Block = DepthwiseSeparableConv

    def __init__(self, widths=(8, 16, 32, 32), n_classes: int = 10, lr: float = 0.01,
                 epochs: int = 20, batch_size: int = 64, random_state: int = 0) -> None:
        if len(widths) < 2 or any(int(w) < 1 for w in widths):
            raise ValueError("widths 至少要两段且全为正整数，如 (8,16,32,32)")
        self.widths, self.n_classes, self.lr = tuple(int(w) for w in widths), n_classes, lr
        self.epochs, self.batch_size, self.random_state = epochs, batch_size, random_state
        self.classes_, self._built = None, False
        self.history: dict[str, list[float]] = {"loss": [], "train_acc": []}

    def init(self):
        rng, w = np.random.default_rng(self.random_state), self.widths
        self.stem, self.stem_bn = Conv2D(w[0], 1, 3, 1, rng=rng), BatchNorm(w[0])
        self.blocks = [self.Block(w[i], w[i + 1], rng) for i in range(len(w) - 1)]
        self.head_W = rng.normal(0.0, np.sqrt(2.0 / w[-1]), size=(w[-1], self.n_classes))
        self.head_b, self.dhead_W = np.zeros(self.n_classes), np.zeros_like(self.head_W)
        self.dhead_b = np.zeros_like(self.head_b)
        self._params = ([p for m in [self.stem, self.stem_bn, *self.blocks] for p in m._params]
                        + [(self.head_W, self.dhead_W), (self.head_b, self.dhead_b)])
        self._adam, self._t, self._built = {}, 0, True
        return self

    def n_params(self) -> int:
        return int(sum(p.size for p, _ in (self._params if self._built else self.init()._params)))

    def _forward(self, X, training: bool):
        z = self.stem_bn.forward(self.stem.forward(X), training)
        self._stem_z, x = z, relu(z)
        self._pools = []
        for block in self.blocks:
            x = block.forward(x, training)
            shape = x.shape
            x, idx = maxpool_forward(x)
            self._pools.append((idx, shape))
        self._feat, self._gap_shape = x.mean(axis=(2, 3)), x.shape
        return softmax(self._feat @ self.head_W + self.head_b)

    def _backward(self, proba, y1):
        d = (proba - y1) / len(proba)
        self.dhead_W[...], self.dhead_b[...] = self._feat.T @ d, d.sum(axis=0)
        d = d @ self.head_W.T
        H, W = self._gap_shape[2:]
        d = np.repeat(np.repeat(d[:, :, None, None], H, axis=2), W, axis=3) / (H * W)
        for block, (idx, shape) in zip(reversed(self.blocks), reversed(self._pools)):
            d = block.backward(maxpool_backward(d, idx, shape))
        return self.stem.backward(self.stem_bn.backward(d * relu_grad(self._stem_z)))

    def _step(self) -> None:
        self._t += 1
        for i, (p, g) in enumerate(self._params):
            st = self._adam.setdefault(i, {"m": np.zeros_like(p), "v": np.zeros_like(p)})
            st["m"], st["v"] = 0.9 * st["m"] + 0.1 * g, 0.999 * st["v"] + 0.001 * g * g
            mh, vh = st["m"] / (1 - 0.9 ** self._t), st["v"] / (1 - 0.999 ** self._t)
            p -= self.lr * mh / (np.sqrt(vh) + 1e-8)

    def fit(self, X, y):
        X, y = np.asarray(X, dtype=float), np.asarray(y)
        if X.ndim != 4 or X.shape[1] != 1 or X.shape[2] != X.shape[3] or y.ndim != 1:
            raise ValueError("X 应为 (N,1,H,W) 方形灰度图，y 为一维标签")
        if len(X) != len(y):
            raise ValueError("X 与 y 的样本数不一致")
        self.classes_, yi = np.unique(y, return_inverse=True)
        if len(self.classes_) != self.n_classes:
            raise ValueError("y 的类别数与 n_classes 不符")
        self.init()
        rng, y1 = np.random.default_rng(self.random_state), np.eye(self.n_classes)[yi]
        self.history = {"loss": [], "train_acc": []}
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            for s in range(0, len(X), self.batch_size):
                idx = order[s:s + self.batch_size]
                self._backward(self._forward(X[idx], training=True), y1[idx])
                self._step()
            proba = self._forward(X, training=False)
            correct = proba[np.arange(len(X)), yi]
            self.history["loss"].append(float(-np.mean(np.log(np.clip(correct, 1e-12, 1.0)))))
            self.history["train_acc"].append(float(np.mean(proba.argmax(axis=1) == yi)))
        return self

    def predict_proba(self, X):
        if not self._built:
            raise RuntimeError("网络尚未构建：先调用 fit(X, y) 或 init()")
        return self._forward(np.asarray(X, dtype=float), training=False)

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


class MobileNetLite(_ConvNet):
    """深度可分离网络：stem + 3 个 DS 块（每块后池化）+ GAP + 线性头。"""
    Block = DepthwiseSeparableConv


class StandardCNN(_ConvNet):
    """同通道数对照：结构/池化/线性头相同，DS 块换标准 3×3 卷积。"""
    Block = StandardBlock
