"""参考解：第 4 题（实现）——Pocket 感知机

    uv run python sol-04-Pocket.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import Perceptron  # noqa: E402


class PocketPerceptron(Perceptron):
    def fit(self, X, y):
        super().fit(X, y)
        best_acc, best = -1.0, (self.w.copy(), self.b)
        best_history = []
        for w, b in self.param_history:
            self.w, self.b = w, b
            a = float(np.mean(self.predict(X) == y))
            best_history.append(a)
            if a > best_acc:
                best_acc, best = a, (w.copy(), b)
        self.w, self.b = best
        self.best_acc_ = best_acc
        # 恢复最后一次的“原始”快照，便于对比
        self.last_w, self.last_b = self.param_history[-1]
        return self


def main() -> None:
    X_tr, X_te, y_tr, y_te = D.make_overlap()
    pocket = PocketPerceptron(lr=0.05, epochs=100, random_state=0).fit(X_tr, y_tr)
    last_w, last_b = pocket.last_w, pocket.last_b

    pocket_acc = float(np.mean(pocket.predict(X_te) == y_te))
    # 用最后一次快照评估
    tmp = Perceptron(lr=0.05, epochs=1, standardize=False)
    tmp.w, tmp.b = last_w, last_b
    tmp._mu = pocket._mu
    tmp._sigma = pocket._sigma
    last_acc = float(np.mean(tmp.predict(X_te) == y_te))

    print(f"最后一次更新：测试 acc {last_acc:.4f}")
    print(f"Pocket 最优：  测试 acc {pocket_acc:.4f}（训练最优 {pocket.best_acc_:.4f}）")
    assert pocket_acc >= last_acc - 1e-12
    print("\n→ Pocket 保留历史最优，避免“越训越差”；但仍不保证收敛，也不改变线性边界。")


if __name__ == "__main__":
    main()
