"""DQN 的独立基线：随机策略 + 表格 Q 学习。

用途：
- `random_policy`：下界，证明"学习确实发生了"；
- `tabular_q`：同一环境下**不用神经网络、不用 replay、不用 target network** 的经典
  Q-learning，作为 DQN 的算法基线，同时充当 replay/target 的消融参照。

只复用 `impl.GridWorld` 的环境（同一个 4×4 网格、同一套奖励），不复用 `impl.DQN`
的任何训练逻辑，保证基线独立。
"""

from __future__ import annotations

import numpy as np
from impl import GOAL, GridWorld, N


def random_policy(episodes=20, seed=0):
    """均匀随机策略的成功率。"""
    rng = np.random.default_rng(seed)
    env = GridWorld()
    wins = []
    for _ in range(episodes):
        env.reset()
        done = False
        while not done:
            _, _, done = env.step(int(rng.integers(4)))
        wins.append(1.0 if env.pos == GOAL else 0.0)
    return float(np.mean(wins))


def tabular_q(episodes=1000, alpha=0.1, gamma=0.9, epsilon=0.2,
              max_steps=50, seed=0):
    """表格 Q-learning：无 replay、无 target network，返回 Q 表。"""
    rng = np.random.default_rng(seed)
    Q = np.zeros((N * N, 4))
    env = GridWorld(max_steps)
    for _ in range(episodes):
        env.reset()
        s = env.pos
        done = False
        while not done:
            if rng.random() < epsilon:
                a = int(rng.integers(4))
            else:
                a = int(np.argmax(Q[s]))
            _, r, done = env.step(a)
            s2 = env.pos
            target = r + (0.0 if done else gamma * float(Q[s2].max()))
            Q[s, a] += alpha * (target - Q[s, a])
            s = s2
    return Q


def evaluate_q(Q, episodes=20, max_steps=50):
    """贪心执行 Q 表，返回成功率。"""
    env = GridWorld(max_steps)
    wins = []
    for _ in range(episodes):
        env.reset()
        s = env.pos
        done = False
        while not done:
            a = int(np.argmax(Q[s]))
            _, _, done = env.step(a)
            s = env.pos
        wins.append(1.0 if env.pos == GOAL else 0.0)
    return float(np.mean(wins))


if __name__ == "__main__":
    raise SystemExit("本文件是基线库，入口是 demo.py：uv run python demo.py")
