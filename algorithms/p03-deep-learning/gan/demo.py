"""GAN — demo：2D/8×8、非饱和损失、模式崩塌与多样性

    uv run python demo.py

    实验一  2D 8-Gaussians：non-saturating vs saturating vs 小容量
    实验二  8×8 digits：生成样本与“预测类别多样性”
    实验三  手写 vs torch（2D）
"""

from __future__ import annotations

import time

import framework
import numpy as np
from impl import GAN, mode_coverage
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

SEED = 0


def gaussians(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    centers = np.array([[np.cos(a), np.sin(a)] for a in np.linspace(0, 2 * np.pi, 4,
                                                                   endpoint=False)]) * 2
    X = np.vstack([c + rng.normal(0, 0.1, size=(n // 4, 2)) for c in centers])
    return X, centers


def digits_data(n_train=1200):
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(len(X), -1)
    return train_test_split(X, y, train_size=n_train, random_state=SEED, stratify=y)


def entropy(counts):
    p = counts / max(counts.sum(), 1)
    return float(-np.sum(p[p > 0] * np.log(p[p > 0])))


def experiment_2d() -> None:
    X, centers = gaussians()
    print("== 实验一：2D 4-Gaussians（500 轮） ==")
    print(f"{'配置':28} | {'覆盖':>5} | {'熵':>5} | {'NN距':>5} | {'D acc':>5}")
    print("-" * 62)
    configs = [
        ("non-sat, latent=16", dict(latent_dim=16, hidden=(64, 64), loss_type="non_saturating")),
        ("saturating, latent=16", dict(latent_dim=16, hidden=(64, 64), loss_type="saturating")),
        ("collapsed, latent=1", dict(latent_dim=1, hidden=(8, 8), loss_type="non_saturating")),
    ]
    results = {}
    for name, kw in configs:
        m = GAN(data_dim=2, lr_g=5e-4, lr_d=5e-5, g_steps=1,
                random_state=SEED, **kw).train(X, epochs=500, batch_size=64)
        met = mode_coverage(m.sample(500), centers)
        results[name] = met
        print(f"{name:28} | {met['covered']}/4 | {met['entropy']:5.2f} | "
              f"{met['nn_distance']:5.2f} | {m.d_acc_history[-1]:5.2f}")
    assert results["non-sat, latent=16"]["covered"] >= 3
    assert results["collapsed, latent=1"]["covered"] < 3
    print("\n→ 非饱和 + 足够容量覆盖 4 个模态；小容量/饱和损失在同样预算下掉队。\n")


def experiment_digits() -> None:
    X_tr, X_te, y_tr, y_te = digits_data()
    clf = LogisticRegression(max_iter=5000).fit(X_tr, y_tr)
    t0 = time.perf_counter()
    gan = GAN(data_dim=64, latent_dim=16, hidden=(32,), lr_g=2e-4, lr_d=5e-5,
              loss_type="non_saturating", out_sigmoid=True, g_steps=2,
              random_state=SEED).train(X_tr, epochs=150, batch_size=64)
    t = time.perf_counter() - t0
    s = gan.sample(256)
    counts = np.bincount(clf.predict(s), minlength=10)
    print("== 实验二：8×8 digits GAN（150 轮） ==")
    print(f"生成 256 张：预测类别 {int(np.sum(counts > 0))}/10，"
          f"类别熵 {entropy(counts):.2f}，耗时 {t:.1f}s，D acc {gan.d_acc_history[-1]:.2f}")
    print("各类计数：" + "、".join(str(int(c)) for c in counts))
    assert np.sum(counts > 0) >= 3
    print("\n→ 8×8 像素的 MLP GAN 只能生成“像数字的模糊块”，类别多样性有限；")
    print("  这也是 DCGAN/条件 GAN 出现的动机。\n")


def experiment_torch() -> None:
    X, centers = gaussians()
    hand = GAN(data_dim=2, latent_dim=16, hidden=(64, 64), lr_g=5e-4, lr_d=5e-5,
               random_state=SEED).train(X, epochs=1000, batch_size=64)
    torch_gan = framework.TorchGAN(data_dim=2, latent_dim=16, hidden=(64, 64),
                                   lr_g=5e-4, lr_d=5e-5, random_state=SEED)
    t0 = time.perf_counter()
    torch_gan.train(X, epochs=1000, batch_size=64)
    t = time.perf_counter() - t0
    mh = mode_coverage(hand.sample(500), centers)
    mt = mode_coverage(torch_gan.sample(500), centers)
    print("== 实验三：手写 vs torch（2D，1000 轮） ==")
    print(f"手写：覆盖 {mh['covered']}/{mh['n_modes']}，熵 {mh['entropy']:.2f}")
    print(f"torch：覆盖 {mt['covered']}/{mt['n_modes']}，熵 {mt['entropy']:.2f}，耗时 {t:.1f}s")
    print()


def main() -> None:
    experiment_2d()
    experiment_digits()
    experiment_torch()


if __name__ == "__main__":
    main()
