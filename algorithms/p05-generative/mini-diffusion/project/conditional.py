"""迁移项目：class-conditional DDPM + CFG

    uv run python conditional.py

训练条件 DDPM，按类别采样并用分类器评估类别一致性；验收 acc > 0.9。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import DDPM  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    Xtr, Xte, ytr, yte = train_test_split(X, y, train_size=1200, random_state=0,
                                          stratify=y)
    clf = LogisticRegression(max_iter=5000).fit(Xtr, ytr)
    d = DDPM(n_steps=100, epochs=100, num_classes=10, hidden=128, random_state=0)
    d.train(Xtr, ytr)
    labels = np.tile(np.arange(10), 20)
    s = d.sample(len(labels), labels=labels, guidance=3.0, seed=1)
    acc = float((clf.predict(s) == labels).mean())
    print(f"train loss：{d.loss_history[-1]:.3f}")
    print(f"CFG w=3 class acc：{acc:.3f}")
    assert acc > 0.9
    print("→ 条件是有效的；但分类器 acc 只是代理，视觉质量仍受 MLP/8×8 限制。")


if __name__ == "__main__":
    main()
