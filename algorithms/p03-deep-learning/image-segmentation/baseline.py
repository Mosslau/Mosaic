"""图像分割基线 — 逐像素逻辑回归 + Otsu 阈值（对照版，允许用 sklearn）。

两个基线都**只看单个像素的灰度**，没有任何空间上下文：

- `PixelLogistic`：把 32×32 图拉平成 1024 个独立样本，用像素灰度预测该像素
  是否属于前景；模型等价于一个"学出来的阈值"，但用同样的标签监督训练，
  所以与 TinyUNet 的差距可以直接归因于"没有局部上下文"。
- `OtsuSegmenter`：无监督地最大化类间方差选全局阈值，作为经典图像处理参照。

两者都在同一 train/test 划分上评估，指标复用 impl.py 的手写 IoU/Dice。
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


class PixelLogistic:
    """逐像素逻辑回归：输入只有 1 维（灰度），没有卷积/邻域。"""

    def __init__(self, max_iter: int = 300, random_state: int = 0) -> None:
        self.max_iter = max_iter
        self.random_state = random_state

    def fit(self, X: np.ndarray, y: np.ndarray):
        x = np.asarray(X, dtype=float).reshape(-1, 1)
        t = np.asarray(y, dtype=float).reshape(-1) > 0.5
        self.clf = LogisticRegression(max_iter=self.max_iter,
                                      random_state=self.random_state).fit(x, t)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        x = np.asarray(X, dtype=float).reshape(-1, 1)
        return self.clf.predict_proba(x)[:, 1].reshape(np.shape(X))

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        return self.predict_proba(X) > threshold


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    """Otsu：在 [0,1] 直方图上选使类间方差最大的阈值。"""
    v = np.asarray(values, dtype=float).ravel()
    hist, edges = np.histogram(v, bins=bins, range=(0.0, 1.0))
    centers = (edges[:-1] + edges[1:]) / 2
    p = hist / max(hist.sum(), 1)
    omega = np.cumsum(p)
    mu = np.cumsum(p * centers)
    denom = omega * (1.0 - omega)
    sigma_b = np.where(denom > 1e-12, (mu[-1] * omega - mu) ** 2 / np.maximum(denom, 1e-12), 0.0)
    return float(centers[int(np.argmax(sigma_b))])


class OtsuSegmenter:
    """无监督全局阈值分割。"""

    def fit(self, X: np.ndarray, y: np.ndarray | None = None):
        self.threshold = otsu_threshold(X)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(X, dtype=float) > self.threshold

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(X, dtype=float)


if __name__ == "__main__":
    raise SystemExit("本文件是对照实现库，实验入口是 demo.py：uv run python demo.py")
