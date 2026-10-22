"""AutoEncoder — demo：压缩、2D latent、PCA 对比与 denoising

    uv run python demo.py

    实验一  2D 压缩：AE vs PCA（重构 MSE）
    实验二  latent 维度扫描：AE vs PCA
    实验三  denoising：干净训练 vs 加噪训练
    实验四  手写 vs torch
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import AutoEncoder
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split

SEED = 0


def load_data(n_train: int = 1200):
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(len(X), -1)
    return train_test_split(X, y, train_size=n_train, random_state=SEED, stratify=y)


def mse(a, b) -> float:
    return float(np.mean((np.asarray(a) - np.asarray(b)) ** 2))


def _median_time(fn, repeats=2):
    times, result = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


def experiment_2d() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    ae, t_ae = _median_time(lambda: AutoEncoder(latent_dim=2, lr=0.01, epochs=100,
                                                batch_size=64, random_state=SEED).fit(X_tr))
    torch_ae, t_torch = _median_time(lambda: framework.TorchAE(
        latent_dim=2, lr=0.01, epochs=100, batch_size=64, random_state=SEED).fit(X_tr))
    pca = PCA(n_components=2).fit(X_tr)
    pca_err = mse(pca.inverse_transform(pca.transform(X_te)), X_te)

    print("== 实验一：2D 压缩（测试 MSE） ==")
    print(f"{'方法':12} | {'MSE':>8} | {'耗时(s)':>7}")
    print("-" * 32)
    for name, m, t in (("手写 AE", ae, t_ae), ("torch AE", torch_ae, t_torch),
                       ("PCA", pca, 0.0)):
        err = pca_err if name == "PCA" else m.reconstruction_error(X_te)
        print(f"{name:12} | {err:8.4f} | {t:7.2f}")
    assert ae.reconstruction_error(X_te) < pca_err
    print("\n→ 2D 瓶颈下 AE 的非线性重构优于线性 PCA。\n")


def experiment_latent() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    print("== 实验二：latent 维度扫描（测试 MSE） ==")
    print(f"{'latent':>6} | {'AE':>8} | {'PCA':>8}")
    print("-" * 28)
    for lat in (2, 4, 8, 16, 32):
        ae = AutoEncoder(latent_dim=lat, lr=0.01, epochs=100, random_state=SEED).fit(X_tr)
        pca = PCA(n_components=lat).fit(X_tr)
        pe = mse(pca.inverse_transform(pca.transform(X_te)), X_te)
        print(f"{lat:6d} | {ae.reconstruction_error(X_te):8.4f} | {pe:8.4f}")
    print("\n→ 低维（≤16）AE 优于 PCA；32 维 PCA 已接近无损，AE 反而略差。\n")


def experiment_denoising() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    rng = np.random.default_rng(SEED)
    noisy = np.clip(X_te + rng.normal(0, 0.3, X_te.shape), 0, 1)
    print("== 实验三：denoising（latent=8） ==")
    print(f"{'训练':14} | {'干净 MSE':>9} | {'加噪 MSE':>9}")
    print("-" * 38)
    clean = AutoEncoder(latent_dim=8, epochs=100, denoising=0.0, random_state=SEED).fit(X_tr)
    denoise = AutoEncoder(latent_dim=8, epochs=100, denoising=0.3, random_state=SEED).fit(X_tr)
    for name, m in (("干净训练", clean), ("加噪训练", denoise)):
        print(f"{name:14} | {m.reconstruction_error(X_te):9.4f} | "
              f"{m.reconstruction_error(noisy):9.4f}")
    assert denoise.reconstruction_error(noisy) < clean.reconstruction_error(noisy)
    print("\n→ 加噪训练牺牲一点干净重构，换来更强的去噪能力。\n")


def experiment_torch() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    print("== 实验四：手写 vs torch（latent=8） ==")
    hand = AutoEncoder(latent_dim=8, epochs=100, random_state=SEED).fit(X_tr)
    torch_ae = framework.TorchAE(latent_dim=8, epochs=100, random_state=SEED).fit(X_tr)
    print(f"手写 MSE {hand.reconstruction_error(X_te):.4f}；"
          f"torch MSE {torch_ae.reconstruction_error(X_te):.4f}")
    print()


def main() -> None:
    experiment_2d()
    experiment_latent()
    experiment_denoising()
    experiment_torch()


if __name__ == "__main__":
    main()
