"""迁移项目：latent 容量与模式覆盖

    uv run python latent_sweep.py

固定 2D 4-Gaussians、500 轮，扫 latent=1/2/8/16，比较覆盖数、熵、NN 距离。
目标：把“模式崩塌”变成可复现的容量实验，而不是只看几张图。
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import GAN, mode_coverage  # noqa: E402


def main() -> None:
    rng = np.random.default_rng(0)
    centers = np.array([[-2.0, 0.0], [2.0, 0.0], [0.0, -2.0], [0.0, 2.0]])
    X = np.vstack([c + rng.normal(0, 0.1, size=(1000, 2)) for c in centers])
    print(f"{'latent':>6} | {'覆盖':>5} | {'熵':>5} | {'NN距':>5} | {'D acc':>5}")
    print("-" * 42)
    rows = {}
    for lat in (1, 2, 8, 16):
        g = GAN(data_dim=2, latent_dim=lat, hidden=(64, 64), lr_g=5e-4, lr_d=5e-5,
                loss_type="non_saturating", random_state=0).train(X, epochs=500,
                                                                 batch_size=64)
        m = mode_coverage(g.sample(500), centers)
        rows[lat] = m
        print(f"{lat:6d} | {m['covered']}/4 | {m['entropy']:5.2f} | "
              f"{m['nn_distance']:5.2f} | {g.d_acc_history[-1]:5.2f}")

    print("\n== 验收 ==")
    checks = [
        ("最大覆盖 ≥3/4", max(m["covered"] for m in rows.values()) >= 3),
        ("latent=1 覆盖 < 最佳", rows[1]["covered"] < rows[16]["covered"]),
        ("最佳熵 ≥1.0", max(m["entropy"] for m in rows.values()) >= 1.0),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks)
    print("\n→ 容量不是越大越好，但太小（latent=1）会明显限制覆盖。")


if __name__ == "__main__":
    main()
