"""迁移项目：新随机块图上的节点分类"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
from impl import GCN, make_sbm  # noqa: E402


def main() -> None:
    A, X, y = make_sbm(40, 0.2, 0.08, 8, seed=1)
    tr = np.zeros(len(y), bool)
    for c in (0, 1):
        tr[np.where(y == c)[0][:8]] = True
    m = GCN(16, 2, 0.2, 200, 0)
    p = m.fit_predict(A, X, y, tr)
    acc = (p[~tr] == y[~tr]).mean()
    print(f"nodes {len(y)}, test acc {acc:.3f}")
    assert acc > 0.75


if __name__ == "__main__":
    main()
