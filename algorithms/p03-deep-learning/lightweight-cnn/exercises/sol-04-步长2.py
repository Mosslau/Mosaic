"""参考解 4：stride-2 depthwise（MobileNet 的下采样方式）。

pad=1、stride=2、每通道一个 3×3 核；16×16 → 8×8。
用另一种实现（sliding_window_view）对前向，有限差分对反向。
"""

import sys
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def dw2_forward(X, K):
    """X: (N,C,H,W)，K: (C,3,3) → (N,C,H//2,W//2)。"""
    N, C, H, W = X.shape
    if H % 2 or W % 2:
        raise ValueError("stride-2 depthwise 要求偶数尺寸")
    Xp = np.pad(X, ((0, 0), (0, 0), (1, 1), (1, 1)))
    out = np.zeros((N, C, H // 2, W // 2))
    for i in range(H // 2):
        for j in range(W // 2):
            win = Xp[:, :, 2 * i:2 * i + 3, 2 * j:2 * j + 3]
            out[:, :, i, j] = np.einsum("nchw,chw->nc", win, K)
    return out


def dw2_reference(X, K):
    """独立实现：滑动窗口后隔 2 取一个位置。"""
    Xp = np.pad(X, ((0, 0), (0, 0), (1, 1), (1, 1)))
    win = sliding_window_view(Xp, (3, 3), axis=(2, 3))[:, :, ::2, ::2]
    return np.einsum("nchwuv,cuv->nchw", win, K)


def dw2_backward(X, K, dout):
    """返回 (dX, dK)；重叠窗口对 dX 累加。"""
    N, C, H, W = X.shape
    Xp = np.pad(X, ((0, 0), (0, 0), (1, 1), (1, 1)))
    dXp, dK = np.zeros_like(Xp), np.zeros_like(K)
    for i in range(H // 2):
        for j in range(W // 2):
            win = Xp[:, :, 2 * i:2 * i + 3, 2 * j:2 * j + 3]
            dK += np.einsum("nc,nchw->chw", dout[:, :, i, j], win)
            dXp[:, :, 2 * i:2 * i + 3, 2 * j:2 * j + 3] += dout[:, :, i, j, None, None] * K
    return dXp[:, :, 1:-1, 1:-1], dK


rng = np.random.default_rng(0)
X = rng.normal(size=(2, 3, 8, 8))
K = rng.normal(size=(3, 3, 3))
out = dw2_forward(X, K)
print("shape:", out.shape)
assert out.shape == (2, 3, 4, 4)
assert np.allclose(out, dw2_reference(X, K), atol=1e-12)

G = rng.normal(size=out.shape)
dX, dK = dw2_backward(X, K, G)


def loss() -> float:
    return float(np.sum(dw2_forward(X, K) * G))


eps = 1e-5
for name, arr, grad in (("K", K, dK), ("X", X, dX)):
    worst = 0.0
    for _ in range(3):
        idx = tuple(int(rng.integers(0, s)) for s in arr.shape)
        old = arr[idx]
        arr[idx] = old + eps
        lp = loss()
        arr[idx] = old - eps
        lm = loss()
        arr[idx] = old
        worst = max(worst, abs((lp - lm) / (2 * eps) - grad[idx]))
    print(f"{name} 最大梯度误差: {worst:.2e}")
    assert worst < 1e-6
print("stride-2 depthwise 前向/反向验证通过")
