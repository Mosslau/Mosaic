"""参考解：第 4 题（实现）——denoising AE

    uv run python sol-04-去噪.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import AutoEncoder  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(len(X), -1)
    X_tr, X_te, _, _ = train_test_split(X, y, train_size=600, random_state=0, stratify=y)
    rng = np.random.default_rng(0)
    noisy = np.clip(X_te + rng.normal(0, 0.3, X_te.shape), 0, 1)
    clean = AutoEncoder(latent_dim=8, epochs=80, denoising=0.0, random_state=0).fit(X_tr)
    denoise = AutoEncoder(latent_dim=8, epochs=80, denoising=0.3, random_state=0).fit(X_tr)
    print(f"干净训练：干净 {clean.reconstruction_error(X_te):.4f}，"
          f"加噪 {clean.reconstruction_error(noisy):.4f}")
    print(f"加噪训练：干净 {denoise.reconstruction_error(X_te):.4f}，"
          f"加噪 {denoise.reconstruction_error(noisy):.4f}")
    assert denoise.reconstruction_error(noisy) < clean.reconstruction_error(noisy)


if __name__ == "__main__":
    main()
