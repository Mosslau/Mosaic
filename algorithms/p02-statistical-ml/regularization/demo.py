"""正则化与模型选择 — demo：Ridge / Lasso / 交叉验证 / 偏差-方差

    uv run python demo.py

产出五张表：
    手算示例     两个特征、λ=1 的 Ridge 闭式解
    实验一       Ridge 正则路径（系数收缩）+ sklearn 对照
    实验二       Lasso 正则路径（稀疏化）+ sklearn 对照
    实验三       K 折交叉验证选 λ（只用训练集），再报告测试 MSE
    实验四       偏差-方差分解：模型复杂度（多项式次数）的 U 形曲线
"""

from __future__ import annotations

import framework
import impl
import numpy as np
from impl import Lasso, Ridge, cross_val_mse, mse
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 80
TRUE_W = np.array([3.0, -2.0, 1.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


# ---------------------------------------------------------------- 数据

def make_sparse(n: int = 200, p: int = 10, noise: float = 1.0,
                seed: int = SEED):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, p))
    y = X @ TRUE_W[:p] + 0.5 + rng.normal(0.0, noise, n)
    return X, y


def true_f(x: np.ndarray) -> np.ndarray:
    return np.sin(1.5 * x)


def poly_features(x: np.ndarray, degree: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return np.column_stack([x ** k for k in range(1, degree + 1)])


# ---------------------------------------------------------------- 手算示例

def experiment_hand_calc() -> dict:
    X = np.array([[1.0, 0.0], [0.0, 1.0]])
    y = np.array([2.0, 4.0])
    lam = 1.0
    w, b = impl.ridge_closed_form(X, y, lam)
    print("== 手算示例：X = I₂，y = [2, 4]，λ = 1 ==")
    print("  中心化：x̄ = [0.5, 0.5]，ȳ = 3；Xc = [[0.5,−0.5],[−0.5,0.5]]，yc = [−1, 1]")
    print("  XcᵀXc = [[0.5,−0.5],[−0.5,0.5]]，nλI = 2I")
    print(f"  解 (XcᵀXc + nλI)w = Xcᵀyc → w = {np.round(w, 4).tolist()}，b = {b:.4f}")
    print(f"  预测：{np.round(X @ w + b, 4).tolist()}（λ=0 时 w=[−1, 1]、b=3，预测 [2, 4]）")
    assert np.allclose(w, [-1 / 3, 1 / 3]) and abs(b - 3.0) < 1e-12
    print("→ L2 把 [−1, 1] 向 0 收缩到 [−1/3, 1/3]：模长变小、预测变「钝」。\n")
    return {"w": w, "b": b}


# ---------------------------------------------------------------- 实验一

def experiment_ridge_path() -> list:
    X, y = make_sparse()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED)
    print("== 实验一：Ridge 正则路径（10 维、只有 3 个真实特征） ==")
    print(f"{'λ':>7} | {'‖w‖':>7} | {'训练 MSE':>9} | {'测试 MSE':>9}")
    print("-" * 44)
    rows = []
    for lam in (0.0, 0.01, 0.1, 1.0, 10.0, 100.0):
        model = Ridge(lam=lam).fit(X_tr, y_tr)
        tr = mse(y_tr, model.predict(X_tr))
        te = mse(y_te, model.predict(X_te))
        rows.append({"lam": lam, "norm": float(np.linalg.norm(model.coef)),
                     "train": tr, "test": te})
        print(f"{lam:7.2f} | {rows[-1]['norm']:7.4f} | {tr:9.4f} | {te:9.4f}")

    sk = framework.fit_ridge(X_tr, y_tr, lam=1.0)
    hand = Ridge(lam=1.0).fit(X_tr, y_tr)
    diff = float(np.max(np.abs(hand.coef - sk.coef_)))
    print(f"\nλ=1 时手写与 sklearn 的系数最大差：{diff:.2e}"
          f"（sklearn alpha = n·λ = {len(y_tr)}）")
    assert diff < 1e-8, "Ridge 闭式解应与 sklearn 一致（注意 alpha=n·λ 的换算）"
    assert rows[0]["norm"] > rows[-1]["norm"], "‖w‖ 应随 λ 增大而收缩"
    assert rows[-1]["train"] > rows[0]["train"], "训练 MSE 应随 λ 增大而上升"
    print("→ λ 越大系数越靠近 0、训练误差越大；本数据 n≫p、信噪比高，测试误差整体上升——\n"
          "   正则化的收益要在「小样本 / 高维 / 强共线」上才明显（见实验三）。\n")
    return rows


# ---------------------------------------------------------------- 实验二

def experiment_lasso_path() -> list:
    X, y = make_sparse()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED)
    print("== 实验二：Lasso 正则路径（坐标下降） ==")
    print(f"{'λ':>7} | {'非零个数':>6} | {'非零特征':>18} | {'训练 MSE':>9} | {'测试 MSE':>9}")
    print("-" * 66)
    rows = []
    for lam in (0.01, 0.05, 0.1, 0.2, 0.5, 1.0):
        model = Lasso(lam=lam).fit(X_tr, y_tr)
        nz = np.flatnonzero(np.abs(model.coef) > 1e-8)
        tr = mse(y_tr, model.predict(X_tr))
        te = mse(y_te, model.predict(X_te))
        rows.append({"lam": lam, "nz": len(nz), "idx": nz.tolist(),
                     "train": tr, "test": te})
        print(f"{lam:7.2f} | {len(nz):6d} | {str(nz.tolist()):>18} | {tr:9.4f} | {te:9.4f}")

    sk = framework.fit_lasso(X_tr, y_tr, lam=0.1)
    hand = Lasso(lam=0.1).fit(X_tr, y_tr)
    diff = float(np.max(np.abs(hand.coef - sk.coef_)))
    print(f"\nλ=0.1 时手写与 sklearn 的系数最大差：{diff:.2e}（同口径：alpha = λ）")
    assert diff < 1e-5, "坐标下降应与 sklearn Lasso 一致"
    assert rows[0]["nz"] >= rows[-1]["nz"], "λ 越大非零系数应越少"
    assert rows[-1]["nz"] <= 3, "λ=1 时应只剩 3 个以内的真实特征"
    print("→ L1 把不重要的系数压到**恰好 0**；λ 越大越稀疏。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_cv() -> dict:
    X, y = make_sparse(n=200, noise=3.0, seed=1)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED)
    lams = np.logspace(-3, 1, 25)
    print("== 实验三：5 折交叉验证选 λ（只在训练集上做） ==")
    print(f"{'λ':>8} | {'CV MSE':>8} | {'测试 MSE':>9}")
    print("-" * 32)
    rows = []
    for lam in lams:
        cv, folds = cross_val_mse(lambda lam=lam: Ridge(lam=lam), X_tr, y_tr, k=5, seed=0)
        model = Ridge(lam=lam).fit(X_tr, y_tr)
        te = mse(y_te, model.predict(X_te))
        rows.append({"lam": float(lam), "cv": cv, "test": te})
        print(f"{lam:8.4f} | {cv:8.4f} | {te:9.4f}")

    best = min(rows, key=lambda r: r["cv"])
    zero = next(r for r in rows if r["lam"] <= 1e-3 + 1e-12)
    print(f"\n选中的 λ = {best['lam']:.4f}（CV MSE {best['cv']:.4f}）；"
          f"λ≈0 的 CV MSE {zero['cv']:.4f}，测试 MSE {zero['test']:.4f}")
    print(f"选中 λ 的测试 MSE = {best['test']:.4f}")

    # sklearn 的 5 折复算
    cv_sk, _ = framework.cv_mse_ridge(X_tr, y_tr, best["lam"], k=5, seed=0)
    print(f"sklearn cross_val_score 复算同一 λ：{cv_sk:.4f}")
    assert abs(cv_sk - best["cv"]) < 1e-6, "手写 KFold 应与 sklearn KFold 对齐"
    assert best["lam"] > 1e-3, "本数据上 CV 应选中正的正则强度"
    assert best["test"] <= zero["test"] * 1.02, "CV 选出的 λ 不应差于 λ≈0"
    print("→ CV 只用训练集选 λ；测试集只用来报告最终结果。\n")
    return {"best": best, "zero": zero, "rows": rows}


# ---------------------------------------------------------------- 实验四

def experiment_bias_variance() -> list:
    rng = np.random.default_rng(SEED)
    x_test = np.linspace(-3, 3, 200)
    f_test = true_f(x_test)
    print(f"== 实验四：偏差-方差分解（{REPEATS} 次重复采样，n=30，噪声 0.4） ==")
    print(f"{'次数':>4} | {'bias²':>8} | {'variance':>9} | {'总误差':>8} | {'训练 MSE':>9}")
    print("-" * 54)
    rows = []
    for degree in range(1, 10):
        preds = np.zeros((REPEATS, len(x_test)))
        train_mses = []
        for r in range(REPEATS):
            x = rng.uniform(-3, 3, 30)
            y = true_f(x) + rng.normal(0, 0.4, 30)
            Xtr = poly_features(x, degree)
            Xte = poly_features(x_test, degree)
            model = Ridge(lam=0.0, standardize=True).fit(Xtr, y)
            preds[r] = model.predict(Xte)
            train_mses.append(mse(y, model.predict(Xtr)))
        mean_pred = preds.mean(axis=0)
        bias2 = float(np.mean((mean_pred - f_test) ** 2))
        var = float(np.mean(preds.var(axis=0)))
        rows.append({"degree": degree, "bias2": bias2, "var": var,
                     "mse": bias2 + var, "train": float(np.mean(train_mses))})
        print(f"{degree:>4} | {bias2:8.4f} | {var:9.4f} | {bias2 + var:8.4f} | "
              f"{rows[-1]['train']:9.4f}")

    best = min(rows, key=lambda r: r["mse"])
    assert 1 < best["degree"] < 9, "最优复杂度应在中间（U 形）"
    assert rows[-1]["var"] > rows[best["degree"] - 1]["var"] * 5, "高次项的方差应显著更大"
    print(f"\n→ 最优次数 = {best['degree']}；欠拟合端偏差大、过拟合端方差大。\n")
    return rows


def main() -> None:
    experiment_hand_calc()
    experiment_ridge_path()
    experiment_lasso_path()
    experiment_cv()
    experiment_bias_variance()


if __name__ == "__main__":
    main()
