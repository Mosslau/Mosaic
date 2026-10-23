"""DDPM — demo：前向加噪、去噪采样、class-conditional + CFG

    uv run python demo.py
"""

from __future__ import annotations

import time

import framework
import numpy as np
from impl import DDPM
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    Xtr, Xte, ytr, yte = train_test_split(X, y, train_size=1200, random_state=0,
                                          stratify=y)
    clf = LogisticRegression(max_iter=5000).fit(Xtr, ytr)

    print("== 实验一：DDPM 训练（100 步，100 轮） ==")
    d = DDPM(n_steps=100, epochs=100, num_classes=10, hidden=128, random_state=0)
    t0 = time.perf_counter()
    d.train(Xtr, ytr, batch_size=64)
    t_train = time.perf_counter() - t0
    print(f"train loss：{d.loss_history[0]:.3f} → {d.loss_history[-1]:.3f}；{t_train:.1f}s")

    print("\n== 实验二：无条件采样 ==")
    t0 = time.perf_counter()
    un = d.sample(16, seed=1)
    t_sample = time.perf_counter() - t0
    print(f"sample(16)：{un.shape}，范围 [{un.min():.3f}, {un.max():.3f}]，{t_sample:.2f}s")

    print("\n== 实验三：class-conditional + CFG ==")
    labels = np.tile(np.arange(10), 20)   # 200 个样本，每类 20 个
    print(f"{'w':>4} | {'class acc':>9} | {'diversity':>9}")
    print("-" * 32)
    best = None
    for w in (0.0, 1.0, 3.0, 7.0):
        s = d.sample(len(labels), labels=labels, guidance=w, seed=1)
        acc = float((clf.predict(s) == labels).mean())
        div = float(np.mean(np.linalg.norm(s[:, None] - s[None, :], axis=2)))
        print(f"{w:4.1f} | {acc:9.3f} | {div:9.2f}")
        if best is None or acc > best[1]:
            best = (w, acc)
    print(f"→ 最佳 w={best[0]}（class acc {best[1]:.3f}）；w=0 是无条件。\n")

    print("== 实验四：手写 vs torch（w=3） ==")
    fm = framework.run_framework(Xtr, ytr, labels, n_steps=100, epochs=100, guidance=3.0)
    acc = float((clf.predict(fm["samples"]) == labels).mean())
    print(f"torch：loss {fm['loss']:.3f}；class acc {acc:.3f}；"
          f"train {fm['time_sec']:.1f}s / sample {fm['sample_time']:.2f}s")


if __name__ == "__main__":
    main()
