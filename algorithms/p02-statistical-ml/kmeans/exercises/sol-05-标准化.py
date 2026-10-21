"""参考解：第 5 题（迁移）——标准化对 digits 聚类的影响

    uv run python sol-05-标准化.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import KMeans  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    raw = KMeans(n_clusters=10, n_init=5, random_state=0).fit(X)
    std = KMeans(n_clusters=10, n_init=5, random_state=0).fit(
        StandardScaler().fit_transform(X))
    ari_raw = adjusted_rand_score(y, raw.labels_)
    ari_std = adjusted_rand_score(y, std.labels_)
    print(f"原始像素：ARI {ari_raw:.3f}，inertia {raw.inertia_:.0f}")
    print(f"标准化后：ARI {ari_std:.3f}，inertia {std.inertia_:.0f}")
    assert np.isfinite(ari_raw) and np.isfinite(ari_std)
    assert abs(ari_raw - ari_std) > 0.05, "本数据上两者应有可见差异"
    print("\n→ 标准化不是'总是更好'：它解决量纲问题，但可能破坏像素结构；要按数据验证。")


if __name__ == "__main__":
    main()
