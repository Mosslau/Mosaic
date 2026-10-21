"""参考解：第 4 题（实现）——自动找肘部

    uv run python sol-04-肘部.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import make_blobs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import KMeans  # noqa: E402


def elbow_k(X, max_k=8):
    ks = np.arange(1, max_k + 1, dtype=float)
    inertia = np.array([KMeans(n_clusters=int(k), n_init=10, random_state=0)
                        .fit(X).inertia_ for k in ks])
    x = (ks - ks.min()) / (ks.max() - ks.min())
    y = (inertia - inertia.min()) / (inertia.max() - inertia.min())
    # 首尾连线：x + y = 1；距离 = |x + y − 1| / √2
    dist = np.abs(x + y - 1.0)
    return int(ks[int(np.argmax(dist))]), inertia


def main() -> None:
    X, _ = make_blobs(n_samples=300, centers=3, cluster_std=0.7, random_state=0)
    k, inertia = elbow_k(X)
    print("inertia：" + "、".join(f"k={i + 1}:{v:.1f}" for i, v in enumerate(inertia)))
    print(f"肘部 k = {k}")
    assert k == 3, "3 团数据的肘部应为 3"
    print("→ 归一化后找离首尾连线最远的点，比肉眼判断更可复现。")


if __name__ == "__main__":
    main()
