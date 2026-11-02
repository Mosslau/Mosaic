"""DQN — demo：网格世界上的 Q 学习"""

from __future__ import annotations

import time

import numpy as np
from baseline import evaluate_q, random_policy, tabular_q
from impl import DQN


def main() -> None:
    print("4×4 网格：起点 0，目标 15，无陷阱；动作 上/下/左/右")
    t0 = time.perf_counter()
    m = DQN(hidden=32, lr=0.01, gamma=0.9, epsilon=0.2, target_every=20).fit(
        episodes=1000, max_steps=50, seed=0)
    dt = time.perf_counter() - t0
    print(f"训练 {dt:.2f}s；末 100 轮成功率 {np.mean(m.success[-100:]):.2f}")
    print(f"贪心评估成功率 {m.evaluate(20):.2f}")
    print(f"随机策略成功率 {random_policy(20):.2f}")
    Q = tabular_q(episodes=1000, alpha=0.1, gamma=0.9, epsilon=0.2, seed=0)
    print(f"表格 Q 基线成功率 {evaluate_q(Q):.2f}（无 replay / 无 target）")
    print(f"loss {m.loss_history[0]:.3f} → {m.loss_history[-1]:.3f}")
    print(f"策略（每个格子的动作）：{m.policy()}")
    assert m.evaluate(20) >= 0.8
    assert evaluate_q(Q) >= 0.8


if __name__ == "__main__":
    main()
