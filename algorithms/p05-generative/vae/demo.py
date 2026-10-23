"""VAE — demo：ELBO、2D latent、采样/插值、与 p03 AE 对照

    uv run python demo.py
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import framework
import numpy as np
from impl import VAE
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

BASE = Path(__file__).resolve().parent


def load_ae():
    path = BASE.parent.parent / "p03-deep-learning" / "autoencoder" / "impl.py"
    spec = importlib.util.spec_from_file_location("p03_ae", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.AutoEncoder


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    Xtr, Xte, ytr, yte = train_test_split(X, y, train_size=1200, random_state=0,
                                          stratify=y)

    print("== 实验一：VAE vs p03 AutoEncoder（latent=2，100 轮） ==")
    t0 = time.perf_counter()
    vae = VAE(latent_dim=2, beta=1.0, epochs=100, random_state=0).fit(Xtr)
    t_vae = time.perf_counter() - t0
    vae_mse = float(np.mean((vae.reconstruct(Xte) - Xte) ** 2))

    AutoEncoder = load_ae()
    ae = AutoEncoder(latent_dim=2, epochs=100, random_state=0).fit(Xtr)
    ae_mse = ae.reconstruction_error(Xte)
    print(f"VAE : test MSE {vae_mse:.4f}，KL {vae.kl_history[-1]:.3f}，{t_vae:.1f}s")
    print(f"AE  : test MSE {ae_mse:.4f}")
    print("VAE 能 sample()；AE 只能 reconstruct()，不能从先验采样。\n")

    print("== 实验二：beta 权衡（recon / KL） ==")
    print(f"{'beta':>5} | {'test MSE':>8} | {'KL':>6}")
    print("-" * 26)
    for beta in (0.1, 1.0, 4.0):
        v = VAE(latent_dim=2, beta=beta, epochs=100, random_state=0).fit(Xtr)
        mse = float(np.mean((v.reconstruct(Xte) - Xte) ** 2))
        print(f"{beta:5.1f} | {mse:8.4f} | {v.kl_history[-1]:6.3f}")
    print()

    print("== 实验三：先验采样 + 插值 ==")
    s = vae.sample(8)
    print(f"sample(8) 形状 {s.shape}，范围 [{s.min():.3f}, {s.max():.3f}]")
    mu, _ = vae.encode(Xte[:2])
    interp = vae.interpolate(mu[0], mu[1], 5)
    print(f"interpolate(2→5) 形状 {interp.shape}；相邻 L2 变化 "
          f"{np.mean(np.linalg.norm(np.diff(interp, axis=0), axis=1)):.3f}\n")

    print("== 实验四：手写 vs torch ==")
    fm = framework.run_framework(Xtr, Xte, latent_dim=2, beta=1.0, epochs=100)
    print(f"VAE 手写 test MSE {vae_mse:.4f} / {t_vae:.1f}s")
    print(f"VAE torch  test MSE {fm['mse']:.4f} / {fm['time_sec']:.1f}s")


if __name__ == "__main__":
    main()
