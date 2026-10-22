"""参考解：第 5 题（迁移）——T 的影响

    uv run python sol-05-T扫描.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import LSTM, RNN  # noqa: E402


def parity(n, T, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(n, T))
    y = X.sum(axis=1) % 2
    return np.eye(2)[X], y


def main() -> None:
    print(f"{'T':>3} | {'RNN acc':>8} | {'LSTM acc':>8} | {'RNN |dh0|':>10}")
    print("-" * 38)
    for T in (4, 8, 12):
        X, y = parity(3000, T)
        Xtr, Xte, ytr, yte = X[:2400], X[2400:], y[:2400], y[2400:]
        rnn = RNN(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=40,
                  batch_size=32, clip_norm=1.0, random_state=0).fit(Xtr, ytr)
        lstm = LSTM(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=40,
                    batch_size=32, clip_norm=1.0, random_state=0).fit(Xtr, ytr)
        a1 = float(np.mean(rnn.predict(Xte) == yte))
        a2 = float(np.mean(lstm.predict(Xte) == yte))
        gn = rnn.grad_norm_h0_for_T(Xte, yte)
        print(f"{T:3d} | {a1:8.3f} | {a2:8.3f} | {gn:10.2e}")
    print("\n→ RNN 随 T 变长明显退化；LSTM 更稳。")


if __name__ == "__main__":
    main()
