"""DQN — 性质测试"""

import numpy as np
import pytest
from baseline import evaluate_q, random_policy, tabular_q
from impl import DQN, GOAL, GridWorld, QNet


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


@pytest.mark.parametrize("name,idx", [
    ("W1", (0, 0)),
    ("b1", (0,)),
    ("W2", (0, 0)),
    ("b2", (0,)),
])
def test_qnet_gradients(name, idx) -> None:
    """Q 网络四组参数的有限差分（固定 dout，loss=sum(out*dout)）。"""
    q = QNet(hidden=8, seed=0)
    rng = np.random.default_rng(0)
    X = rng.normal(size=(5, 16))
    dout = rng.normal(size=(5, 4))
    q.forward(X)
    q.backward(dout, lr=0.0, step=False)

    def loss():
        return float((q.forward(X) * dout).sum())

    eps = 1e-6
    param = q._params()[name]
    analytic = float(q._grads()[name][idx])
    old = param[idx]
    param[idx] = old + eps
    lp = loss()
    param[idx] = old - eps
    lm = loss()
    param[idx] = old
    assert abs((lp - lm) / (2 * eps) - analytic) < 1e-4, name


def test_seed_variance() -> None:
    accs = []
    for seed in (0, 1, 2):
        m = DQN(seed=seed).fit(1000, 50, seed)
        accs.append(m.evaluate(20))
    assert min(accs) >= 0.8, accs


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


def test_baseline_random_policy() -> None:
    p = random_policy(20, seed=0)
    assert 0.0 <= p <= 1.0


def test_baseline_tabular_q_learns() -> None:
    Q = tabular_q(episodes=1000, alpha=0.1, gamma=0.9, epsilon=0.2, seed=0)
    assert evaluate_q(Q, episodes=20) >= 0.8


def test_baseline_tabular_deterministic() -> None:
    a = tabular_q(episodes=50, seed=0)
    b = tabular_q(episodes=50, seed=0)
    np.testing.assert_array_equal(a, b)
