"""DQN — 手写实现：网格世界 + Q 网络 + replay + target network"""

from __future__ import annotations

from collections import deque

import numpy as np

N = 4
GOAL = 15
HOLES = set()  # 教学版不设陷阱；可自行加入 {5,7,11}
ACTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # 上/下/左/右


class GridWorld:
    def __init__(self, max_steps=50):
        self.max_steps = max_steps
        self.reset()

    def reset(self):
        self.pos = 0
        self.steps = 0
        return self.state()

    def state(self):
        s = np.zeros(N * N)
        s[self.pos] = 1.0
        return s

    def step(self, a):
        if a not in range(4):
            raise ValueError("动作必须在 0..3")
        self.steps += 1
        r, c = divmod(self.pos, N)
        dr, dc = ACTIONS[a]
        r, c = min(N - 1, max(0, r + dr)), min(N - 1, max(0, c + dc))
        self.pos = r * N + c
        if self.pos == GOAL:
            return self.state(), 1.0, True
        if self.pos in HOLES:
            return self.state(), -1.0, True
        if self.steps >= self.max_steps:
            return self.state(), -0.01, True
        return self.state(), -0.01, False


class QNet:
    def __init__(self, hidden=32, seed=0):
        rng = np.random.default_rng(seed)
        self.W1 = rng.normal(0, np.sqrt(2 / 16), (16, hidden))
        self.b1 = np.zeros(hidden)
        self.W2 = rng.normal(0, np.sqrt(2 / hidden), (hidden, 4))
        self.b2 = np.zeros(4)
        self.hidden = hidden

    def forward(self, X):
        self.X = np.asarray(X, dtype=float)
        self.H = np.maximum(0, self.X @ self.W1 + self.b1)
        return self.H @ self.W2 + self.b2

    def backward(self, dout, lr):
        dW2 = self.H.T @ dout
        db2 = dout.sum(0)
        dH = (dout @ self.W2.T) * (self.H > 0)
        dW1 = self.X.T @ dH
        db1 = dH.sum(0)
        for p, g in ((self.W1, dW1), (self.b1, db1), (self.W2, dW2), (self.b2, db2)):
            p -= lr * g

    def copy_from(self, other):
        self.W1, self.b1 = other.W1.copy(), other.b1.copy()
        self.W2, self.b2 = other.W2.copy(), other.b2.copy()


class DQN:
    def __init__(self, hidden=32, lr=0.01, gamma=0.9, epsilon=0.2,
                 batch_size=32, memory=2000, target_every=20, seed=0):
        if not (0 <= epsilon <= 1) or batch_size < 1:
            raise ValueError("参数非法")
        self.q = QNet(hidden, seed)
        self.target = QNet(hidden, seed)
        self.target.copy_from(self.q)
        self.lr, self.gamma, self.epsilon = lr, gamma, epsilon
        self.batch_size, self.memory, self.target_every = batch_size, memory, target_every
        self.buffer = deque(maxlen=memory)
        self.steps = 0
        self.loss_history = []

    def act(self, state, rng=None):
        if rng is None:
            rng = np.random.default_rng()
        if rng.random() < self.epsilon:
            return int(rng.integers(4))
        return int(np.argmax(self.q.forward(state[None])[0]))

    def remember(self, s, a, r, s2, done):
        self.buffer.append((s, a, r, s2, done))

    def train_step(self):
        if len(self.buffer) < self.batch_size:
            return
        rng = np.random.default_rng(self.steps)
        idx = rng.choice(len(self.buffer), self.batch_size, replace=False)
        batch = [self.buffer[i] for i in idx]
        S = np.stack([b[0] for b in batch])
        A = np.array([b[1] for b in batch])
        R = np.array([b[2] for b in batch])
        S2 = np.stack([b[3] for b in batch])
        D = np.array([b[4] for b in batch], dtype=float)
        q = self.q.forward(S)
        q_next = self.target.forward(S2).max(1)
        target = R + self.gamma * q_next * (1 - D)
        dq = np.zeros_like(q)
        dq[np.arange(len(A)), A] = (q[np.arange(len(A)), A] - target)
        self.q.backward(dq / len(A), self.lr)
        self.loss_history.append(float(np.mean((q[np.arange(len(A)), A] - target) ** 2)))
        self.steps += 1
        if self.steps % self.target_every == 0:
            self.target.copy_from(self.q)

    def fit(self, episodes=200, max_steps=50, seed=0):
        rng = np.random.default_rng(seed)
        env = GridWorld(max_steps)
        self.success = []
        for _ in range(episodes):
            s = env.reset()
            done = False
            while not done:
                a = self.act(s, rng)
                s2, r, done = env.step(a)
                self.remember(s, a, r, s2, done)
                self.train_step()
                s = s2
            self.success.append(1.0 if env.pos == GOAL else 0.0)
        return self

    def policy(self):
        return [int(np.argmax(self.q.forward(np.eye(16)[i][None])[0])) for i in range(16)]

    def evaluate(self, episodes=20, max_steps=50):
        env = GridWorld(max_steps)
        wins = []
        for _ in range(episodes):
            s = env.reset()
            done = False
            while not done:
                a = int(np.argmax(self.q.forward(s[None])[0]))
                s, _, done = env.step(a)
            wins.append(1.0 if env.pos == GOAL else 0.0)
        return float(np.mean(wins))


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
