"""参考解：第 4 题（实现）——多头拆/拼

    uv run python sol-04-多头.py
"""

import numpy as np


def split_heads(X, H):
    N, T, D = X.shape
    return X.reshape(N, T, H, D // H).transpose(0, 2, 1, 3)


def merge_heads(X):
    N, H, T, Dh = X.shape
    return X.transpose(0, 2, 1, 3).reshape(N, T, H * Dh)


def main() -> None:
    X = np.random.default_rng(0).normal(size=(2, 5, 8))
    Y = merge_heads(split_heads(X, 2))
    print(f"roundtrip 最大差：{np.abs(X - Y).max():.2e}")
    assert np.allclose(X, Y)


if __name__ == "__main__":
    main()
