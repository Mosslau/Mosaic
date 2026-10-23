"""DQN — 性质测试"""

import numpy as np
import pytest
from impl import DQN, GOAL, GridWorld


def test_env_goal() -> None:
    env = GridWorld()
    env.reset()
    for a in (1, 1, 1, 3, 3, 3):
        _, _, done = env.step(a)
    assert done and env.pos == GOAL


def test_env_invalid() -> None:
    with pytest.raises(ValueError):
        GridWorld().step(4)


def test_q_shape() -> None:
    m = DQN()
    q = m.q.forward(np.eye(16)[0][None])
    assert q.shape == (1, 4)


def test_replay_and_loss() -> None:
    m = DQN(batch_size=8)
    env = GridWorld()
    s = env.reset()
    for _ in range(20):
        a = int(np.random.default_rng(0).integers(4))
        s2, r, done = env.step(a)
        m.remember(s, a, r, s2, done)
        s = env.reset() if done else s2
        m.train_step()
    assert len(m.buffer) > 0
    assert m.loss_history and np.isfinite(m.loss_history[-1])


def test_learns() -> None:
    m = DQN(lr=0.01, gamma=0.9, epsilon=0.2).fit(1000, 50, 0)
    assert m.evaluate(20) >= 0.8


def test_policy_shape() -> None:
    m = DQN().fit(10, 20, 0)
    assert len(m.policy()) == 16
    assert set(m.policy()) <= {0, 1, 2, 3}


def test_invalid() -> None:
    with pytest.raises(ValueError):
        DQN(epsilon=1.5)
    with pytest.raises(ValueError):
        DQN(batch_size=0)


def test_deterministic() -> None:
    a = DQN().fit(50, 20, 0)
    b = DQN().fit(50, 20, 0)
    assert a.policy() == b.policy()
