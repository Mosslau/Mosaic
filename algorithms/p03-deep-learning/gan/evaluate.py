"""GAN 固定评估协议：类别覆盖/熵/多样性。"""

from __future__ import annotations

import numpy as np


def digit_metrics(samples, classifier, n_classes=10, min_frac=0.01):
    """对 8×8 digits 生成样本做固定协议评估。

    - coverage：预测类别中占比 ≥ min_frac 的类别数；
    - entropy：预测类别分布的熵；
    - unique：生成样本去重比例；
    - nn_distance：样本间最近邻平均距离。
    """
    S = np.asarray(samples, float)
    if S.ndim != 2 or len(S) < 2:
        raise ValueError("samples 应为至少 2 行的二维数组")
    pred = classifier.predict(S)
    counts = np.bincount(pred, minlength=n_classes).astype(float)
    frac = counts / max(counts.sum(), 1)
    covered = int(np.sum(frac >= min_frac))
    p = frac[frac > 0]
    ent = float(-np.sum(p * np.log(p)))
    unique = float(len(np.unique(S, axis=0)) / len(S))
    dists = np.linalg.norm(S[:, None, :] - S[None, :, :], axis=2)
    nn = float(np.mean(np.partition(dists, 2, axis=1)[:, 1]))
    return {"coverage": covered, "entropy": ent, "unique": unique,
            "nn_distance": nn, "counts": counts.astype(int)}


if __name__ == "__main__":
    raise SystemExit("本文件是评估库，由 demo.py / 测试调用")
