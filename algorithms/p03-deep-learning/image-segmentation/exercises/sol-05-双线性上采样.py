"""参考解 05（实现）：双线性上采样 forward / backward + 伴随检查。

运行：cd exercises && uv run python sol-05-双线性上采样.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from impl import upsample_backward, upsample_nearest  # noqa: E402


def _axis_weights(n_in: int, scale: int):
    """align_corners=False 的源坐标、左右下标与权重。"""
    src = (np.arange(n_in * scale) + 0.5) / scale - 0.5
    i0 = np.floor(src).astype(int)
    w = src - i0
    return np.clip(i0, 0, n_in - 1), np.clip(i0 + 1, 0, n_in - 1), w


def bilinear_upsample(X: np.ndarray, scale: int = 2) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    N, C, H, W = X.shape
    y0, y1, wy = _axis_weights(H, scale)
    x0, x1, wx = _axis_weights(W, scale)
    out = np.empty((N, C, H * scale, W * scale))
    for oy in range(H * scale):
        for ox in range(W * scale):
            out[:, :, oy, ox] = (
                (1 - wy[oy]) * (1 - wx[ox]) * X[:, :, y0[oy], x0[ox]]
                + (1 - wy[oy]) * wx[ox] * X[:, :, y0[oy], x1[ox]]
                + wy[oy] * (1 - wx[ox]) * X[:, :, y1[oy], x0[ox]]
                + wy[oy] * wx[ox] * X[:, :, y1[oy], x1[ox]]
            )
    return out


def bilinear_backward(dout: np.ndarray, scale: int = 2) -> np.ndarray:
    """双线性上采样的转置：把每个输出像素的梯度按四个权重累加回输入。"""
    N, C, H, W = dout.shape[0], dout.shape[1], dout.shape[2] // scale, dout.shape[3] // scale
    y0, y1, wy = _axis_weights(H, scale)
    x0, x1, wx = _axis_weights(W, scale)
    dX = np.zeros((N, C, H, W))
    for oy in range(H * scale):
        for ox in range(W * scale):
            g = dout[:, :, oy, ox]
            dX[:, :, y0[oy], x0[ox]] += g * (1 - wy[oy]) * (1 - wx[ox])
            dX[:, :, y0[oy], x1[ox]] += g * (1 - wy[oy]) * wx[ox]
            dX[:, :, y1[oy], x0[ox]] += g * wy[oy] * (1 - wx[ox])
            dX[:, :, y1[oy], x1[ox]] += g * wy[oy] * wx[ox]
    return dX


def main() -> None:
    toy = np.array([[[[0.0, 1.0], [2.0, 3.0]]]])
    expected = np.array([[0.0, 0.25, 0.75, 1.0],
                         [0.5, 0.75, 1.25, 1.5],
                         [1.5, 1.75, 2.25, 2.5],
                         [2.0, 2.25, 2.75, 3.0]])
    np.testing.assert_allclose(bilinear_upsample(toy)[0, 0], expected, atol=1e-12)
    print("2×2 → 4×4 双线性结果：")
    print(np.round(bilinear_upsample(toy)[0, 0], 2))

    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, 3, 4, 4))
    G = rng.normal(size=(2, 3, 8, 8))
    lhs = float(np.sum(bilinear_upsample(X) * G))
    rhs = float(np.sum(X * bilinear_backward(G)))
    lhs_n = float(np.sum(upsample_nearest(X) * G))
    rhs_n = float(np.sum(X * upsample_backward(G)))
    print(f"双线性伴随误差 {abs(lhs - rhs):.2e}；最近邻伴随误差 {abs(lhs_n - rhs_n):.2e}")
    assert abs(lhs - rhs) < 1e-10
    assert abs(np.sum(bilinear_upsample(np.ones((1, 1, 4, 4)))) - 64) < 1e-12
    print("✓ 双线性前向值正确、反向是其转置（伴随误差 < 1e-10）")


if __name__ == "__main__":
    main()
