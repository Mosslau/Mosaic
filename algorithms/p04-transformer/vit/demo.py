"""ViT-lite — demo：8×8 图切 4 patch + 自注意力分类"""

from __future__ import annotations

import time

from baseline import fit_baseline
from impl import ViT
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split


def load():
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 1, 8, 8)
    return train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)


def main() -> None:
    Xtr, Xte, ytr, yte = load()
    t0 = time.perf_counter()
    m = ViT(d=64, n_classes=10, lr=0.1, epochs=200, seed=0).fit(Xtr, ytr)
    dt = time.perf_counter() - t0
    acc = (m.predict(Xte) == yte).mean()
    print("patch 4×4 → 4 patch + cls；d=64；单头 1 block")
    base = fit_baseline(Xtr, ytr, Xte, yte)
    print(f"loss {m.loss_history[0]:.3f} → {m.loss_history[-1]:.3f}；测试 acc {acc:.4f}；{dt:.1f}s")
    print(f"逻辑回归基线（展平像素）acc {base:.4f}")
    assert acc > 0.75


if __name__ == "__main__":
    main()
