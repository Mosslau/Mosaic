"""迁移项目：VAE 采样 + latent 插值

    uv run python generate.py

训练 2D VAE，报告重构 MSE、采样形状、插值连续性；验收 MSE < 0.05。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import VAE  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    Xtr, Xte, _, _ = train_test_split(X, y, train_size=1200, random_state=0, stratify=y)
    vae = VAE(latent_dim=2, beta=0.1, epochs=100, random_state=0).fit(Xtr)
    mse = float(np.mean((vae.reconstruct(Xte) - Xte) ** 2))
    s = vae.sample(8)
    mu, _ = vae.encode(Xte[:2])
    interp = vae.interpolate(mu[0], mu[1], 8)
    print(f"test MSE：{mse:.4f}")
    print(f"sample：{s.shape}，范围 [{s.min():.3f}, {s.max():.3f}]")
    print(f"interpolate：{interp.shape}，相邻 L2 平均 "
          f"{np.mean(np.linalg.norm(np.diff(interp, axis=0), axis=1)):.3f}")
    assert mse < 0.05 and np.isfinite(s).all()
    print("→ VAE 能采样和插值；2D latent 下生成偏模糊，但 latent 是连续的。")


if __name__ == "__main__":
    main()
