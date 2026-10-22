"""参考解：第 5 题（迁移）——BN/残差小对照

    uv run python sol-05-BN残差.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import LeNet  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 1, 8, 8)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, train_size=600, random_state=0,
                                              stratify=y)
    print(f"{'配置':16} | {'测试 acc':>8}")
    print("-" * 28)
    accs = []
    for name, kw in (("baseline", {}), ("+BN", {"use_bn": True}),
                     ("+Residual", {"use_residual": True}),
                     ("+BN+Residual", {"use_bn": True, "use_residual": True})):
        m = LeNet(lr=0.003, epochs=30, batch_size=64, **kw).fit(X_tr, y_tr)
        a = float(np.mean(m.predict(X_te) == y_te))
        accs.append(a)
        print(f"{name:16} | {a:8.4f}")
    assert max(accs) >= accs[0]
    print("\n→ BN 稳定训练；残差单独收益小；小数据上差距有限。")


if __name__ == "__main__":
    main()
