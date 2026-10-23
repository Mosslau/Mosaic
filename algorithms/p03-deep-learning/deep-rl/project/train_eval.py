"""迁移项目：训练并评估 DQN"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from impl import DQN  # noqa: E402


def main() -> None:
    m = DQN(lr=.01, gamma=.9, epsilon=.2).fit(1000, 50, 0)
    acc = m.evaluate(20)
    print(f"greedy success {acc:.2f}；loss {m.loss_history[-1]:.3f}")
    assert acc >= .8


if __name__ == "__main__":
    main()
