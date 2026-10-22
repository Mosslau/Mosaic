"""参考解：第 5 题（迁移）——latent 分类

    uv run python sol-05-latent分类.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import AutoEncoder  # noqa: E402


def acc(y, p):
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, train_size=1200, random_state=0,
                                              stratify=y)
    ae = AutoEncoder(latent_dim=8, epochs=80, random_state=0).fit(X_tr)
    pca = PCA(n_components=8).fit(X_tr)
    for name, A, B in (("raw", X_tr, X_te),
                       ("AE8", ae.encode(X_tr), ae.encode(X_te)),
                       ("PCA8", pca.transform(X_tr), pca.transform(X_te))):
        log = LogisticRegression(max_iter=5000).fit(A, y_tr)
        print(f"{name:5} acc {acc(y_te, log.predict(B)):.4f}")


if __name__ == "__main__":
    main()
