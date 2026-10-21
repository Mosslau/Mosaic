"""逻辑回归 — 真实数据附录：概率校准（breast cancer）

    uv run python calibration.py

train/calib/test = 60/20/20：在 train 上拟合手写逻辑回归，
在 calib 上拟合 Platt（对 logit 再做一维逻辑回归），在 test 上比较
Brier 分数与 ECE（期望校准误差）。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from impl import Model  # noqa: E402


def ece(y, p, bins=10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if mask.sum():
            total += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return float(total)


def main() -> None:
    X, y = load_breast_cancer(return_X_y=True)
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.4, random_state=0,
                                                stratify=y)
    X_cal, X_te, y_cal, y_te = train_test_split(X_tmp, y_tmp, test_size=0.5,
                                                random_state=0, stratify=y_tmp)

    model = Model(lr=0.1, epochs=8000, tol=1e-12).fit(X_tr, y_tr)
    p_raw = model.predict_proba(X_te)

    p_cal = model.predict_proba(X_cal)
    z_cal = np.log(np.clip(p_cal, 1e-12, 1 - 1e-12) /
                   np.clip(1 - p_cal, 1e-12, 1 - 1e-12))
    z_te = np.log(np.clip(p_raw, 1e-12, 1 - 1e-12) /
                  np.clip(1 - p_raw, 1e-12, 1 - 1e-12))
    platt = LogisticRegression().fit(z_cal.reshape(-1, 1), y_cal)
    p_platt = platt.predict_proba(z_te.reshape(-1, 1))[:, 1]

    print(f"train {len(y_tr)} / calib {len(y_cal)} / test {len(y_te)}")
    print(f"{'版本':10} | {'Brier':>7} | {'ECE':>7} | {'acc':>6}")
    print("-" * 34)
    for name, p in (("原始", p_raw), ("Platt", p_platt)):
        print(f"{name:10} | {np.mean((p - y_te) ** 2):7.4f} | {ece(y_te, p):7.4f} | "
              f"{np.mean((p >= 0.5) == y_te):6.4f}")
    assert np.mean((p_platt - y_te) ** 2) <= np.mean((p_raw - y_te) ** 2) + 0.005
    print("\n→ 逻辑回归的概率通常已较接近校准；Platt 只在有明显偏差时才带来收益。")


if __name__ == "__main__":
    main()
