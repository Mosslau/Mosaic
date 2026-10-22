"""参考解：第 4 题（实现）——2×2 平均池化

    uv run python sol-04-平均池化.py
"""

import numpy as np


def avgpool_forward(X):
    N, C, H, W = X.shape
    return X.reshape(N, C, H // 2, 2, W // 2, 2).mean(axis=(3, 5))


def avgpool_backward(dout, shape):
    N, C, H, W = shape
    d = np.repeat(np.repeat(dout / 4.0, 2, axis=2), 2, axis=3)
    return d.reshape(N, C, H, W)


def main() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, 3, 8, 8))
    out = avgpool_forward(X)
    G = rng.normal(size=out.shape)
    lhs = np.sum(out * G)
    rhs = np.sum(X * avgpool_backward(G, X.shape))
    print(f"<pool(X),G>={lhs:.6f}，<X,pool'(G)>={rhs:.6f}")
    assert abs(lhs - rhs) < 1e-10
    print("→ 平均池化反向把梯度均分到窗口；与最大池化的 argmax 路由不同。")


if __name__ == "__main__":
    main()
