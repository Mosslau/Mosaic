"""确定性合成分割数据：32×32 灰度图 + 同尺寸二值 mask。

设计目标不是"越真越好"，而是让**逐像素基线必然失败**：
背景是左暗右亮的渐变 + 横向条纹 + 高斯噪声，形状内部更平滑；
圆形的填充灰度（0.28–0.36）落在背景渐变的中段，矩形（0.62–0.78）明显更亮。
于是任何"只看单个像素灰度"的阈值都顾此失彼，必须利用局部上下文。
"""

from __future__ import annotations

import numpy as np
from impl import IMG_SIZE


def _sample_shape(rng: np.random.Generator, yy: np.ndarray, xx: np.ndarray):
    """随机取一个矩形或圆，返回 (mask, 填充灰度)。"""
    cy, cx = rng.integers(9, 23, size=2)
    if rng.random() < 0.5:
        h, w = rng.integers(7, 12, size=2)
        m = (np.abs(yy - cy) < h / 2) & (np.abs(xx - cx) < w / 2)
        value = rng.uniform(0.62, 0.78)      # 矩形：比背景亮
    else:
        r = rng.integers(5, 8)
        m = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
        value = rng.uniform(0.28, 0.36)      # 圆：亮度落在背景渐变中段
    return m, value


def make_dataset(n: int, seed: int = 0, max_shapes: int = 2,
                 allow_overlap: bool = False):
    """生成 n 张 32×32 灰度图与二值 mask；同 seed 逐位可复现。

    allow_overlap=False 时最多尝试 200 次放置，放不下就少放一个形状
    （project 的面积测量需要互不重叠的独立连通域）。
    """
    if n < 1:
        raise ValueError("n 至少为 1")
    if max_shapes < 1:
        raise ValueError("max_shapes 至少为 1")
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:IMG_SIZE, 0:IMG_SIZE].astype(float)
    X = np.empty((n, 1, IMG_SIZE, IMG_SIZE))
    Y = np.empty((n, 1, IMG_SIZE, IMG_SIZE))
    for k in range(n):
        bg = 0.13 + 0.30 * (xx / (IMG_SIZE - 1)) + 0.05 * np.sin(2 * np.pi * yy / 4.5)
        img = bg + rng.normal(0.0, 0.05, size=(IMG_SIZE, IMG_SIZE))
        mask = np.zeros((IMG_SIZE, IMG_SIZE), dtype=bool)
        for _ in range(int(rng.integers(1, max_shapes + 1))):
            for _try in range(200):
                m, value = _sample_shape(rng, yy, xx)
                if allow_overlap or not np.any(m & mask):
                    break
            else:
                continue
            img[m] = value + rng.normal(0.0, 0.025, size=int(m.sum()))
            mask |= m
        X[k, 0] = np.clip(img, 0.0, 1.0)
        Y[k, 0] = mask.astype(float)
    return X, Y


if __name__ == "__main__":
    for split, n, seed in (("train", 320, 11), ("val", 64, 12), ("test", 64, 13)):
        X, Y = make_dataset(n, seed)
        print(f"{split}: X{X.shape} Y{Y.shape} 前景占比 {Y.mean():.4f}")
