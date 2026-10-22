"""参考解：第 5 题（迁移）——隐层宽度/学习率小扫

    uv run python sol-05-调参.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import MLP  # noqa: E402
from test_impl import digits  # noqa: E402


def main() -> None:
    X_tr, X_te, y_tr, y_te = digits()
    X_fit, X_val, y_fit, y_val = train_test_split(X_tr, y_tr, test_size=0.2,
                                                  random_state=1, stratify=y_tr)
    print(f"{'hidden':8} | {'lr':>5} | {'val acc':>7} | {'test acc':>8}")
    print("-" * 38)
    best = None
    for hidden in ((16,), (64,), (128,)):
        for lr in (0.005, 0.01, 0.05):
            m = MLP(hidden_sizes=hidden, lr=lr, epochs=20, batch_size=32,
                    optimizer="adam", random_state=0).fit(X_fit, y_fit)
            va = float(np.mean(m.predict(X_val) == y_val))
            te = float(np.mean(m.predict(X_te) == y_te))
            print(f"{str(hidden):8} | {lr:5.3f} | {va:7.4f} | {te:8.4f}")
            if best is None or va > best[0]:
                best = (va, hidden, lr, te)
    print(f"\n最优：hidden={best[1]} lr={best[2]}，val {best[0]:.4f}，test {best[3]:.4f}")
    assert best[3] >= 0.95
    print("→ 宽度/学习率要和数据量匹配；验证集选参，测试集只报一次。")


if __name__ == "__main__":
    main()
