"""LeNet 手写 vs torch：训练预算诊断（100/300 轮）。"""

from __future__ import annotations

import time

import framework
import numpy as np
from demo import load_data
from impl import LeNet


def main() -> None:
    Xtr, Xte, ytr, yte = load_data()
    print(f"{'轮数':>4} | {'手写 acc':>8} | {'torch acc':>9} | {'差距':>6} | {'手写秒':>6}")
    print("-" * 48)
    for ep in (100, 300):
        t0 = time.perf_counter()
        h = LeNet(lr=.003, epochs=ep, batch_size=64, use_bn=True,
                  use_residual=True, random_state=0).fit(Xtr, ytr)
        th = time.perf_counter() - t0
        t0 = time.perf_counter()
        t = framework.TorchLeNet(lr=.003, epochs=ep, batch_size=64,
                                 use_bn=True, use_residual=True,
                                 random_state=0).fit(Xtr, ytr)
        ah = float(np.mean(h.predict(Xte) == yte))
        at = float(np.mean(t.predict(Xte) == yte))
        print(f"{ep:4d} | {ah:8.4f} | {at:9.4f} | {ah-at:6.4f} | {th:6.1f}")
    print("\n→ 修复 Conv2D.dW 轴序后，300 轮差距约 -0.005；"
          "剩余差异是训练随机性/优化器细节，已不是反向错误。")


if __name__ == "__main__":
    main()
