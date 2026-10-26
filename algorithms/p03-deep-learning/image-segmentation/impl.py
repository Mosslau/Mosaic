"""图像分割 TinyUNet-lite — 手写实现（深度模型 · 判别式）

编码器-解码器，输入输出都是 32×32 单通道：

    conv(1→8,3×3) → ReLU → maxpool2 → conv(8→16,3×3) → ReLU
    → 最近邻上采样×2 → conv(16→8,3×3) → ReLU → 1×1 conv → sigmoid

    model = TinyUNet().fit(X_train, y_train)   # X:(N,1,32,32)，y 同形 0/1
    mask = model.predict(X_test)               # (N,1,32,32) bool

卷积、池化、上采样、BCE 的反向全部由 numpy 手写。本实现只有编码器-解码器骨架，
没有 U-Net 的 skip connection，所以叫 TinyUNet-lite，不是完整 U-Net。
"""

from __future__ import annotations

import numpy as np

IMG_SIZE = 32
IN_SHAPE = (1, IMG_SIZE, IMG_SIZE)


# ---------------------------------------------------------------- 基础算子

def im2col(X: np.ndarray, kh: int, kw: int, stride: int = 1, pad: int = 0) -> np.ndarray:
    """(N,C,H,W) → (N*out_h*out_w, C*kh*kw)，把每个滑窗摊平成一行。"""
    N, C, H, W = X.shape
    if pad:
        X = np.pad(X, ((0, 0), (0, 0), (pad, pad), (pad, pad)))
    Hp, Wp = X.shape[2], X.shape[3]
    out_h, out_w = (Hp - kh) // stride + 1, (Wp - kw) // stride + 1
    cols = np.empty((N, out_h, out_w, C, kh, kw), dtype=X.dtype)
    for i in range(kh):
        for j in range(kw):
            cols[:, :, :, :, i, j] = X[:, :, i:i + stride * out_h:stride,
                                       j:j + stride * out_w:stride].transpose(0, 2, 3, 1)
    return cols.reshape(N * out_h * out_w, C * kh * kw)


def col2im(dcol: np.ndarray, shape: tuple, kh: int, kw: int,
           stride: int = 1, pad: int = 0) -> np.ndarray:
    """im2col 的转置：窗口梯度在重叠位置**累加**回原图。"""
    N, C, H, W = shape
    Hp, Wp = H + 2 * pad, W + 2 * pad
    out_h, out_w = (Hp - kh) // stride + 1, (Wp - kw) // stride + 1
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
    """2×2 最大池化；返回 (输出, 每个窗口最大值的位置 0..3)。"""
    N, C, H, W = X.shape
    if H % 2 or W % 2:
        raise ValueError("2×2 池化要求长宽为偶数")
    x = X.reshape(N, C, H // 2, 2, W // 2, 2).transpose(0, 1, 2, 4, 3, 5)
    x = x.reshape(N, C, H // 2, W // 2, 4)
    idx = x.argmax(axis=-1)
    return np.take_along_axis(x, idx[..., None], axis=-1)[..., 0], idx


def maxpool_backward(dout: np.ndarray, idx: np.ndarray, shape: tuple) -> np.ndarray:
    """梯度只回传给当年取到最大值的那个位置，其余为 0。"""
    N, C, H, W = shape
    d = np.zeros((N, C, H // 2, W // 2, 4), dtype=dout.dtype)
    np.put_along_axis(d, idx[..., None], dout[..., None], axis=-1)
    return d.reshape(N, C, H // 2, W // 2, 2, 2).transpose(0, 1, 2, 4, 3, 5).reshape(N, C, H, W)


def upsample_nearest(X: np.ndarray, scale: int = 2) -> np.ndarray:
    """最近邻上采样：每个像素复制成 scale×scale 块，空间尺寸放大 scale 倍。"""
    if X.ndim != 4:
        raise ValueError("上采样输入应为 (N,C,H,W)")
    return np.repeat(np.repeat(X, scale, axis=2), scale, axis=3)


def upsample_backward(dout: np.ndarray, scale: int = 2) -> np.ndarray:
    """上采样的转置：每个 scale×scale 输出块的梯度**求和**回一个输入像素。"""
    N, C, H, W = dout.shape
    if H % scale or W % scale:
        raise ValueError("上采样反向要求尺寸能被 scale 整除")
    return dout.reshape(N, C, H // scale, scale, W // scale, scale).sum(axis=(3, 5))


def relu(z: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, z)


def relu_grad(z: np.ndarray) -> np.ndarray:
    return (z > 0).astype(float)


def sigmoid(z: np.ndarray) -> np.ndarray:
    """数值稳定版 sigmoid：正负两支分开算，避免 exp 溢出。"""
    out = np.empty_like(z, dtype=float)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def bce_with_logits(logits: np.ndarray, target: np.ndarray) -> float:
    """二分类交叉熵（从 logits 直接算，数值稳定）。"""
    z, t = np.asarray(logits, float), np.asarray(target, float)
    if z.shape != t.shape:
        raise ValueError("logits 与 target 形状必须一致")
    return float((np.maximum(z, 0) - z * t + np.log1p(np.exp(-np.abs(z)))).mean())


# ---------------------------------------------------------------- 指标

def _pair(pred: np.ndarray, target: np.ndarray):
    p, t = np.asarray(pred) > 0.5, np.asarray(target) > 0.5
    if p.shape != t.shape:
        raise ValueError("pred 与 target 形状必须一致")
    return p, t


def iou(pred: np.ndarray, target: np.ndarray) -> float:
    """IoU = |P∩T| / |P∪T|；两者都空时约定为 1。"""
    p, t = _pair(pred, target)
    union = np.logical_or(p, t).sum()
    return 1.0 if union == 0 else float(np.logical_and(p, t).sum() / union)


def dice(pred: np.ndarray, target: np.ndarray) -> float:
    """Dice = 2|P∩T| / (|P|+|T|)；两者都空时约定为 1。"""
    p, t = _pair(pred, target)
    denom = p.sum() + t.sum()
    return 1.0 if denom == 0 else float(2.0 * np.logical_and(p, t).sum() / denom)


def pixel_accuracy(pred: np.ndarray, target: np.ndarray) -> float:
    p, t = _pair(pred, target)
    return float(np.mean(p == t))


# ---------------------------------------------------------------- 层与模型

class Conv2D:
    """3×3/1×1 卷积，stride=1；反向用 im2col/col2im 手写。"""

    def __init__(self, out_channels: int, in_channels: int, k: int,
                 pad: int = 1, rng: np.random.Generator | None = None) -> None:
        rng = rng or np.random.default_rng(0)
        scale = np.sqrt(2.0 / (in_channels * k * k))
        self.W = rng.normal(0.0, scale, size=(out_channels, in_channels, k, k))
        self.b = np.zeros(out_channels)
        self.k, self.pad = k, pad

    def forward(self, X: np.ndarray) -> np.ndarray:
        self.X_shape = X.shape
        self.cols = im2col(X, self.k, self.k, 1, self.pad)
        out = self.cols @ self.W.reshape(self.W.shape[0], -1).T + self.b
        N, _, H, W = X.shape
        oh, ow = H + 2 * self.pad - self.k + 1, W + 2 * self.pad - self.k + 1
        return out.reshape(N, oh, ow, -1).transpose(0, 3, 1, 2)

    def backward(self, dout: np.ndarray) -> np.ndarray:
        d2 = dout.transpose(0, 2, 3, 1).reshape(-1, self.W.shape[0])
        self.dW = (d2.T @ self.cols).reshape(self.W.shape)
        self.db = d2.sum(axis=0)
        dcols = d2 @ self.W.reshape(self.W.shape[0], -1)
        return col2im(dcols, self.X_shape, self.k, self.k, 1, self.pad)


class TinyUNet:
    """编码器-解码器分割网络；接口遵循 fit / predict（深度模型 · 判别式）。"""

    def __init__(self, lr: float = 0.008, epochs: int = 60, batch_size: int = 16,
                 random_state: int = 0) -> None:
        if lr <= 0 or epochs < 1 or batch_size < 1:
            raise ValueError("lr/epochs/batch_size 必须为正")
        self.lr, self.epochs, self.batch_size = lr, epochs, batch_size
        self.random_state = random_state
        self.loss_history: list[float] = []

    def _init_params(self, rng: np.random.Generator) -> None:
        self.conv1 = Conv2D(8, 1, 3, 1, rng)     # → (N,8,32,32)
        self.conv2 = Conv2D(16, 8, 3, 1, rng)    # → (N,16,16,16)
        self.conv3 = Conv2D(8, 16, 3, 1, rng)    # → (N,8,32,32)
        self.head = Conv2D(1, 8, 1, 0, rng)      # → (N,1,32,32)
        self._adam: dict[str, dict] = {}
        self._step = 0

    def _check_xy(self, X: np.ndarray, y: np.ndarray) -> None:
        if X.ndim != 4 or X.shape[1:] != IN_SHAPE:
            raise ValueError("X 形状应为 (N,1,32,32)")
        if y.shape != X.shape or len(X) == 0:
            raise ValueError("y 形状应与 X 一致且样本非空")

    def forward(self, X: np.ndarray):
        """返回 logits 与反向所需 cache。"""
        z1 = self.conv1.forward(np.asarray(X, dtype=float))
        pool_in = relu(z1)
        p, idx = maxpool_forward(pool_in)
        z2 = self.conv2.forward(p)
        u = upsample_nearest(relu(z2))
        z3 = self.conv3.forward(u)
        logits = self.head.forward(relu(z3))
        return logits, {"z1": z1, "idx": idx, "pool_shape": pool_in.shape,
                        "z2": z2, "z3": z3, "logits": logits}

    def backward(self, cache: dict, y: np.ndarray) -> dict:
        d = (sigmoid(cache["logits"]) - y) / len(y)
        d = self.head.backward(d) * relu_grad(cache["z3"])
        d = upsample_backward(self.conv3.backward(d))
        d = self.conv2.backward(d * relu_grad(cache["z2"]))
        d = maxpool_backward(d, cache["idx"], cache["pool_shape"]) * relu_grad(cache["z1"])
        self.conv1.backward(d)
        return {"conv1": (self.conv1.dW, self.conv1.db),
                "conv2": (self.conv2.dW, self.conv2.db),
                "conv3": (self.conv3.dW, self.conv3.db),
                "head": (self.head.dW, self.head.db)}

    def _adam_step(self, grads: dict) -> None:
        self._step += 1
        layers = {"conv1": self.conv1, "conv2": self.conv2,
                  "conv3": self.conv3, "head": self.head}
        for key, layer in layers.items():
            for name, g in zip(("W", "b"), grads[key]):
                st = self._adam.setdefault(
                    f"{key}.{name}", {"m": np.zeros_like(g), "v": np.zeros_like(g)})
                st["m"] = 0.9 * st["m"] + 0.1 * g
                st["v"] = 0.999 * st["v"] + 0.001 * g ** 2
                mh = st["m"] / (1.0 - 0.9 ** self._step)
                vh = st["v"] / (1.0 - 0.999 ** self._step)
                getattr(layer, name)[...] -= self.lr * mh / (np.sqrt(vh) + 1e-8)

    def fit(self, X: np.ndarray, y: np.ndarray):
        X, y = np.asarray(X, float), np.asarray(y, float)
        self._check_xy(X, y)
        rng = np.random.default_rng(self.random_state)
        self._init_params(rng)
        self.loss_history = []
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            total, seen = 0.0, 0
            for s in range(0, len(X), self.batch_size):
                idx = order[s:s + self.batch_size]
                logits, cache = self.forward(X[idx])
                total += bce_with_logits(logits, y[idx]) * len(idx)
                seen += len(idx)
                self._adam_step(self.backward(cache, y[idx]))
            self.loss_history.append(total / seen)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return sigmoid(self.forward(X)[0])

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        return self.predict_proba(X) > threshold

    def count_params(self) -> int:
        return sum(a.size for a in (
            self.conv1.W, self.conv1.b, self.conv2.W, self.conv2.b,
            self.conv3.W, self.conv3.b, self.head.W, self.head.b))


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
