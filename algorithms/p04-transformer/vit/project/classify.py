"""迁移项目：小图 ViT 分类"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import ViT  # noqa: E402
from sklearn.datasets import load_digits  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = (X / 16).reshape(-1, 1, 8, 8)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.3, random_state=0, stratify=y)
    m = ViT(d=64, lr=.1, epochs=200, seed=0).fit(Xtr, ytr)
    acc = (m.predict(Xte) == yte).mean()
    print(f"test acc {acc:.3f}")
    assert acc > .75


if __name__ == "__main__":
    main()
