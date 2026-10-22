"""迁移项目：AE 压缩特征 + 逻辑回归分类

    uv run python compression.py

训练 1200 / 测试 597，比较三种特征：
- raw 64 维像素；
- AE 8 维 latent；
- PCA 8 维。
用同一个逻辑回归做下游分类，看“压缩是否保留判别信息”。
"""

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import AutoEncoder  # noqa: E402


def acc(y, p):
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, train_size=1200, random_state=0,
                                              stratify=y)
    print(f"样本 {len(y)}（训练 {len(X_tr)} / 测试 {len(X_te)}），原始 64 维")

    t0 = time.perf_counter()
    ae = AutoEncoder(latent_dim=8, lr=0.01, epochs=100, random_state=0).fit(X_tr)
    t_ae = time.perf_counter() - t0
    pca = PCA(n_components=8).fit(X_tr)

    feats = {
        "raw-64": (X_tr, X_te),
        "AE-8": (ae.encode(X_tr), ae.encode(X_te)),
        "PCA-8": (pca.transform(X_tr), pca.transform(X_te)),
    }
    print(f"\n{'特征':10} | {'维度':>4} | {'测试 acc':>8}")
    print("-" * 28)
    rows = {}
    for name, (A, B) in feats.items():
        log = LogisticRegression(max_iter=5000).fit(A, y_tr)
        rows[name] = acc(y_te, log.predict(B))
        print(f"{name:10} | {A.shape[1]:4d} | {rows[name]:8.4f}")
    print(f"\nAE 训练耗时：{t_ae:.2f}s")

    print("\n== 验收 ==")
    checks = [
        ("AE-8 acc ≥ 0.92", rows["AE-8"] >= 0.92),
        ("AE-8 比 PCA-8 高", rows["AE-8"] > rows["PCA-8"]),
        ("raw-64 仍是上限", rows["raw-64"] >= rows["AE-8"]),
        ("AE 重构误差 < 0.02", ae.reconstruction_error(X_te) < 0.02),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print("\n→ 8 维 latent 保留了大部分判别信息，但仍不如原始 64 维；有损压缩有代价。")


if __name__ == "__main__":
    main()
