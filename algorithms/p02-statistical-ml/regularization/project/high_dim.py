"""迁移项目：p > n 的高维小样本 —— Lasso 特征选择 + 稳定性筛选

    uv run python high_dim.py

场景：80 个样本、100 个特征（基因/传感器/文本特征都长这样）。普通最小二乘在这里没有
唯一解（p > n）；Ridge 能解但会把 100 个特征全部留下；Lasso 可以把大部分压到 0。

验收标准见 README.md；脚本内逐条断言。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import Lasso, Ridge, cross_val_mse, mse  # noqa: E402

N, P = 80, 100
TRUE_IDX = np.arange(8)
TRUE_W = np.array([5.0, -4.0, 3.0, 2.0, -2.0, 1.5, -1.0, 0.8])
RIDGE_LAMS = np.logspace(-2, 3, 20)
LASSO_LAMS = np.logspace(-3, 1, 25)
STAB_LAM = 0.1          # 比 CV 最优更保守：p≫n 时 CV 偏向预测，不偏向稀疏


def make_data(seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(N, P))
    w = np.zeros(P)
    w[TRUE_IDX] = TRUE_W
    y = X @ w + 0.5 + rng.normal(0.0, 1.5, N)
    return X, y


def cv_curve(make_model, lams, X, y, k=5):
    rows = []
    for lam in lams:
        mean, folds = cross_val_mse(lambda lam=lam: make_model(lam), X, y, k=k, seed=0)
        se = float(np.std(folds, ddof=1) / np.sqrt(len(folds)))
        rows.append((float(lam), mean, se))
    return rows


def one_se(rows):
    best = min(rows, key=lambda r: r[1])
    threshold = best[1] + best[2]
    return max([r for r in rows if r[1] <= threshold], key=lambda r: r[0])


def main() -> None:
    X, y = make_data()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0)
    print(f"样本 {N}、特征 {P}（p > n）；训练 {len(y_tr)} / 测试 {len(y_te)}；"
          f"真实非零特征 {len(TRUE_IDX)} 个")

    ridge_rows = cv_curve(lambda lam: Ridge(lam=lam), RIDGE_LAMS, X_tr, y_tr)
    lasso_rows = cv_curve(lambda lam: Lasso(lam=lam), LASSO_LAMS, X_tr, y_tr)
    ridge_lam = min(ridge_rows, key=lambda r: r[1])[0]
    lasso_lam = min(lasso_rows, key=lambda r: r[1])[0]
    lasso_1se = one_se(lasso_rows)[0]

    ridge = Ridge(lam=ridge_lam).fit(X_tr, y_tr)
    lasso = Lasso(lam=lasso_lam).fit(X_tr, y_tr)

    def summarize(name, model, lam):
        te = mse(y_te, model.predict(X_te))
        nz = np.flatnonzero(np.abs(model.coef) > 1e-8)
        hit = len(set(nz.tolist()) & set(TRUE_IDX.tolist()))
        print(f"{name:6} | λ={lam:8.4f} | 测试 MSE={te:7.3f} | 非零={len(nz):3d} | "
              f"命中 {hit}/8")
        return te, len(nz), hit

    print(f"\n{'方法':6} | {'λ':>8} | {'测试 MSE':>9} | {'非零':>4} | 命中")
    print("-" * 60)
    ridge_test, ridge_nz, _ = summarize("Ridge", ridge, ridge_lam)
    lasso_test, lasso_nz, _ = summarize("Lasso", lasso, lasso_lam)
    print(f"（Lasso 的 1-SE λ = {lasso_1se:.4f}）")

    # 稳定性筛选：bootstrap 30 次，统计每个特征被选中的频率
    rng = np.random.default_rng(0)
    freq = np.zeros(P)
    B = 30
    for _ in range(B):
        idx = rng.integers(0, len(y_tr), len(y_tr))
        model = Lasso(lam=STAB_LAM).fit(X_tr[idx], y_tr[idx])
        freq += (np.abs(model.coef) > 1e-8)
    freq /= B
    selected = np.flatnonzero(freq >= 0.6)
    hit = len(set(selected.tolist()) & set(TRUE_IDX.tolist()))
    true_freq = float(np.mean(freq[TRUE_IDX]))
    noise_max = float(np.max(freq[P - 92:]))   # 后 92 个是噪声特征

    print(f"\n稳定性筛选（λ={STAB_LAM}，bootstrap {B} 次，阈值 0.6）：")
    print(f"  选中 {len(selected)} 个特征，命中真实 {hit}/8；"
          f"真实特征平均频率 {true_freq:.2f}，噪声最高 {noise_max:.2f}")
    top = np.argsort(-freq)[:12]
    for j in top:
        print(f"    x{j:<3} 频率 {freq[j]:.2f}  ({'真实' if j in TRUE_IDX else '噪声'})")

    print("\n== 验收 ==")
    checks = [
        ("Lasso 测试 MSE ≤ Ridge 的 1/2", lasso_test <= ridge_test * 0.5),
        ("Lasso 非零特征 ≤ 60（p=100）", lasso_nz <= 60),
        ("稳定性筛选后 ≤ 20 个特征", len(selected) <= 20),
        ("稳定性筛选命中 ≥ 6/8 个真实特征", hit >= 6),
        ("真实特征平均选中频率 ≥ 0.70", true_freq >= 0.70),
        ("Ridge 几乎不稀疏（非零 ≥ 90）", ridge_nz >= 90),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"

    print(f"\n→ Ridge 保留 {ridge_nz} 个特征、测试 MSE {ridge_test:.1f}；"
          f"Lasso 压到 {lasso_nz} 个、MSE {lasso_test:.1f}；"
          f"稳定性筛选把候选缩到 {len(selected)} 个（{hit} 真 + {len(selected) - hit} 假）。")


if __name__ == "__main__":
    main()
