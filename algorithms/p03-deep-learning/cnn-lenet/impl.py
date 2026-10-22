"""卷积神经网络 LeNet — 手写实现（深度模型 · 判别式）

用 numpy 手写卷积（im2col）、池化反传、BatchNorm、残差与训练循环。
默认输入 8×8（sklearn digits），结构：

    conv1(1→6,3×3,pad1) → [BN] → ReLU → maxpool2
    → conv2(6→16,3×3,pad1) [+ 1×1 skip] → [BN] → ReLU → maxpool2
    → flatten(64) → fc(64→32) → ReLU → fc(32→10) → softmax

    net = LeNet(use_bn=True, use_residual=True).fit(X_train, y_train)
    label = net.predict(X_test)          # X: (N, 1, 8, 8)

手写纪律：卷积/池化/BN/残差反向全部自己写；torch 只在 framework.py 对照。
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------- 基础算子

def im2col(X: np.ndarray, kh: int, kw: int, stride: int = 1, pad: int = 0) -> np.ndarray:
    """(N,C,H,W) → (N*out_h*out_w, C*kh*kw)。重叠窗口会重复取。"""
    N, C, H, W = X.shape
    if pad:
        X = np.pad(X, ((0, 0), (0, 0), (pad, pad), (pad, pad)))
    Hp, Wp = X.shape[2], X.shape[3]
    out_h = (Hp - kh) // stride + 1
    out_w = (Wp - kw) // stride + 1
    cols = np.empty((N, out_h, out_w, C, kh, kw), dtype=X.dtype)
    for i in range(kh):
        for j in range(kw):
            cols[:, :, :, :, i, j] = X[:, :, i:i + stride * out_h:stride,
                                       j:j + stride * out_w:stride].transpose(0, 2, 3, 1)
    return cols.reshape(N * out_h * out_w, C * kh * kw)


def col2im(dcol: np.ndarray, shape: tuple, kh: int, kw: int,
           stride: int = 1, pad: int = 0) -> np.ndarray:
    """im2col 的转置：把窗口梯度按位置累加回 (N,C,H,W)。"""
    N, C, H, W = shape
    Hp, Wp = H + 2 * pad, W + 2 * pad
    out_h = (Hp - kh) // stride + 1
    out_w = (Wp - kw) // stride + 1
    cols = dcol.reshape(N, out_h, out_w, C, kh, kw)
    dX = np.zeros((N, C, Hp, Wp), dtype=dcol.dtype)
    for i in range(kh):
        for j in range(kw):
            dX[:, :, i:i + stride * out_h:stride, j:j + stride * out_w:stride] += \
                cols[:, :, :, :, i, j].transpose(0, 3, 1, 2)
    if pad:
        dX = dX[:, :, pad:pad + H, pad:pad + W]
    return dX


def maxpool_forward(X: np.ndarray):
    N, C, H, W = X.shape
    if H % 2 or W % 2:
        raise ValueError("本实现只支持偶数尺寸的 2×2 池化")
    x = X.reshape(N, C, H // 2, 2, W // 2, 2).transpose(0, 1, 2, 4, 3, 5)
    x = x.reshape(N, C, H // 2, W // 2, 4)
    idx = x.argmax(axis=-1)
    out = np.take_along_axis(x, idx[..., None], axis=-1)[..., 0]
    return out, idx


def maxpool_backward(dout: np.ndarray, idx: np.ndarray, shape: tuple) -> np.ndarray:
    N, C, H, W = shape
    d = np.zeros((N, C, H // 2, W // 2, 4))
    np.put_along_axis(d, idx[..., None], dout[..., None], axis=-1)
    d = d.reshape(N, C, H // 2, W // 2, 2, 2).transpose(0, 1, 2, 4, 3, 5)
    return d.reshape(N, C, H, W)


def relu(z):
    return np.maximum(0.0, z)


def relu_grad(z):
    return (z > 0).astype(float)


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


# ---------------------------------------------------------------- 层

class Conv2D:
    def __init__(self, out_channels: int, in_channels: int, kh: int, kw: int,
                 stride: int = 1, pad: int = 0, rng=None) -> None:
        fan_in = in_channels * kh * kw
        scale = np.sqrt(2.0 / fan_in)
        self.W = rng.normal(0.0, scale, size=(out_channels, in_channels, kh, kw))
        self.b = np.zeros(out_channels)
        self.stride, self.pad = stride, pad

    def forward(self, X):
        self.X_shape = X.shape
        self.cols = im2col(X, self.W.shape[2], self.W.shape[3], self.stride, self.pad)
        out = self.cols @ self.W.reshape(self.W.shape[0], -1).T + self.b
        N, C, H, W = X.shape
        Hp, Wp = H + 2 * self.pad, W + 2 * self.pad
        oh = (Hp - self.W.shape[2]) // self.stride + 1
        ow = (Wp - self.W.shape[3]) // self.stride + 1
        out = out.reshape(N, oh, ow, -1).transpose(0, 3, 1, 2)
        return out

    def backward(self, dout):
        N, C, H, W = self.X_shape
        d2 = dout.transpose(0, 2, 3, 1).reshape(-1, self.W.shape[0])
        self.dW = (self.cols.T @ d2).reshape(self.W.shape)
        self.db = d2.sum(axis=0)
        dcols = d2 @ self.W.reshape(self.W.shape[0], -1)
        dX = col2im(dcols, self.X_shape, self.W.shape[2], self.W.shape[3],
                    self.stride, self.pad)
        return dX


class BatchNorm:
    def __init__(self, channels: int, momentum: float = 0.9, eps: float = 1e-5) -> None:
        self.gamma = np.ones(channels)
        self.beta = np.zeros(channels)
        self.momentum, self.eps = momentum, eps
        self.running_mean = np.zeros(channels)
        self.running_var = np.ones(channels)

    def forward(self, X, training: bool):
        N, C, H, W = X.shape
        x = X.transpose(0, 2, 3, 1).reshape(-1, C)
        if training:
            mean = x.mean(axis=0)
            var = x.var(axis=0)
            self.running_mean = self.momentum * self.running_mean + (1 - self.momentum) * mean
            self.running_var = self.momentum * self.running_var + (1 - self.momentum) * var
        else:
            mean, var = self.running_mean, self.running_var
        std = np.sqrt(var + self.eps)
        xhat = (x - mean) / std
        self.cache = (xhat, std, X.shape)
        out = self.gamma * xhat + self.beta
        return out.reshape(N, H, W, C).transpose(0, 3, 1, 2)

    def backward(self, dout):
        xhat, std, shape = self.cache
        N, C, H, W = shape
        dy = dout.transpose(0, 2, 3, 1).reshape(-1, C)
        self.dgamma = (dy * xhat).sum(axis=0)
        self.dbeta = dy.sum(axis=0)
        dxhat = dy * self.gamma
        dx = (dxhat - dxhat.mean(axis=0) - xhat * (dxhat * xhat).mean(axis=0)) / std
        return dx.reshape(N, H, W, C).transpose(0, 3, 1, 2)


class Linear:
    def __init__(self, in_features: int, out_features: int, rng=None) -> None:
        scale = np.sqrt(2.0 / in_features)
        self.W = rng.normal(0.0, scale, size=(in_features, out_features))
        self.b = np.zeros(out_features)

    def forward(self, X):
        self.X = X
        return X @ self.W + self.b

    def backward(self, dout):
        self.dW = self.X.T @ dout
        self.db = dout.sum(axis=0)
        return dout @ self.W.T


class LeNet:
    def __init__(self, n_classes: int = 10, lr: float = 0.001, epochs: int = 8,
                 batch_size: int = 64, use_bn: bool = False,
                 use_residual: bool = False, optimizer: str = "adam",
                 random_state: int | None = 0) -> None:
        if n_classes < 2:
            raise ValueError("n_classes 至少为 2")
        if optimizer not in ("sgd", "adam"):
            raise ValueError("optimizer 只支持 sgd / adam")
        self.n_classes = n_classes
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.use_bn = use_bn
        self.use_residual = use_residual
        self.optimizer = optimizer
        self.random_state = random_state
        self.loss_history: list[float] = []
        self.filter_history: list[np.ndarray] = []
        self.classes_ = None

    def _init_params(self, rng):
        self.conv1 = Conv2D(6, 1, 3, 3, 1, 1, rng)
        self.bn1 = BatchNorm(6) if self.use_bn else None
        self.conv2 = Conv2D(16, 6, 3, 3, 1, 1, rng)
        self.skip = Conv2D(16, 6, 1, 1, 1, 0, rng) if self.use_residual else None
        self.bn2 = BatchNorm(16) if self.use_bn else None
        self.fc1 = Linear(64, 32, rng)
        self.fc2 = Linear(32, self.n_classes, rng)
        self._adam = {}

    def forward(self, X, training: bool = False):
        x = self.conv1.forward(X)
        if self.bn1 is not None:
            x = self.bn1.forward(x, training)
        self._z1 = x
        x = relu(x)
        p1, idx1 = maxpool_forward(x)

        c2 = self.conv2.forward(p1)
        if self.skip is not None:
            c2 = c2 + self.skip.forward(p1)
        if self.bn2 is not None:
            c2 = self.bn2.forward(c2, training)
        self._z2 = c2
        x = relu(c2)
        p2, idx2 = maxpool_forward(x)
        flat = p2.reshape(len(X), -1)
        self._z_fc1 = self.fc1.forward(flat)
        h = relu(self._z_fc1)
        logits = self.fc2.forward(h)
        return softmax(logits), {"p1_shape": p1.shape, "idx1": idx1, "idx2": idx2,
                                 "p2_shape": p2.shape, "flat": flat, "h": h}

    def backward(self, proba, y_onehot, cache):
        n = len(proba)
        dlogits = (proba - y_onehot) / n
        dh = self.fc2.backward(dlogits)
        drelu = dh * relu_grad(self._z_fc1)
        dflat = self.fc1.backward(drelu)
        dp2 = dflat.reshape(cache["p2_shape"])
        d = maxpool_backward(dp2, cache["idx2"], (len(proba), 16, 4, 4))
        d = d * relu_grad(self._z2)
        if self.bn2 is not None:
            d = self.bn2.backward(d)
        d2 = self.conv2.backward(d)
        if self.skip is not None:
            d2 = d2 + self.skip.backward(d)
        d1 = maxpool_backward(d2, cache["idx1"], (len(proba), 6, 8, 8))
        d1 = d1 * relu_grad(self._z1)
        if self.bn1 is not None:
            d1 = self.bn1.backward(d1)
        self.conv1.backward(d1)
        return self.collect_grads()

    def collect_grads(self):
        g = {"conv1": (self.conv1.dW, self.conv1.db),
             "conv2": (self.conv2.dW, self.conv2.db),
             "fc1": (self.fc1.dW, self.fc1.db),
             "fc2": (self.fc2.dW, self.fc2.db)}
        if self.skip is not None:
            g["skip"] = (self.skip.dW, self.skip.db)
        if self.bn1 is not None:
            g["bn1"] = (self.bn1.dgamma, self.bn1.dbeta)
            g["bn2"] = (self.bn2.dgamma, self.bn2.dbeta)
        return g

    def _apply(self, grads, lr):
        # 把每个参数与梯度配对；实现 Adam（默认）或 SGD
        self._t = getattr(self, "_t", 0) + 1
        pairs = [("conv1", self.conv1, "W"), ("conv1", self.conv1, "b"),
                 ("conv2", self.conv2, "W"), ("conv2", self.conv2, "b"),
                 ("fc1", self.fc1, "W"), ("fc1", self.fc1, "b"),
                 ("fc2", self.fc2, "W"), ("fc2", self.fc2, "b")]
        if self.skip is not None:
            pairs += [("skip", self.skip, "W"), ("skip", self.skip, "b")]
        if self.bn1 is not None:
            pairs += [("bn1", self.bn1, "gamma"), ("bn1", self.bn1, "beta"),
                      ("bn2", self.bn2, "gamma"), ("bn2", self.bn2, "beta")]
        for key, obj, name in pairs:
            g = grads[key][0] if name == "W" else grads[key][1]
            if self.bn1 is not None and key.startswith("bn"):
                g = grads[key][0] if name == "gamma" else grads[key][1]
            p = getattr(obj, name)
            if self.optimizer == "sgd":
                p -= lr * g
            else:
                st = self._adam.setdefault(
                    (key, name), {"m": np.zeros_like(p), "v": np.zeros_like(p)})
                st["m"] = 0.9 * st["m"] + 0.1 * g
                st["v"] = 0.999 * st["v"] + 0.001 * (g ** 2)
                mh = st["m"] / (1 - 0.9 ** self._t)
                vh = st["v"] / (1 - 0.999 ** self._t)
                p -= lr * mh / (np.sqrt(vh) + 1e-8)

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 4 or y.ndim != 1 or len(X) != len(y):
            raise ValueError("X 应为 (N,1,8,8)，y 为一维")
        if X.shape[1:] != (1, 8, 8):
            raise ValueError("本实现固定输入 (N,1,8,8)")
        self.classes_, yi = np.unique(y, return_inverse=True)
        y1 = np.eye(len(self.classes_))[yi]
        rng = np.random.default_rng(self.random_state)
        self._init_params(rng)
        self.loss_history = []
        self.filter_history = []
        self._t = 0
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            for s in range(0, len(X), self.batch_size):
                idx = order[s:s + self.batch_size]
                proba, cache = self.forward(X[idx], training=True)
                grads = self.backward(proba, y1[idx], cache)
                self._apply(grads, self.lr)
            p, _ = self.forward(X, training=False)
            correct = p[np.arange(len(X)), yi]
            self.loss_history.append(float(-np.mean(np.log(np.clip(correct, 1e-12, 1)))))
            self.filter_history.append(self.conv1.W.copy())
        return self

    def predict_proba(self, X):
        p, _ = self.forward(np.asarray(X, dtype=float), training=False)
        return p

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
