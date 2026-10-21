"""线性回归与梯度下降 — demo：同数据双跑 + 四组实验

    uv run python demo.py

产出四张表（数字直接对应 README「实验结果」）：
    实验一  同一份数据上四条路线：手写 GD / 闭式解 / sklearn 闭式解 / sklearn SGD
    实验二  学习率扫描：太小走得慢、太大直接发散
    实验三  标准化对 GD 的影响（同一学习率、不同特征尺度）
    实验四  耗时口径：两种闭式解 vs 手写 GD（重复取中位数）

另加一个「手算示例」打印器：3 个点、一步梯度下降，数字与 README 完全一致。
"""

from __future__ import annotations

import statistics
import time
import warnings

import framework
import impl
import numpy as np
from impl import Model, mse, r2
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 9          # 耗时对比的重复次数（取中位数）
GD_LR = 0.05
GD_EPOCHS = 5000


# ---------------------------------------------------------------- 数据

def make_1d(n: int = 200, seed: int = SEED, noise: float = 1.0):
    """一维数据：y = 3x + 2 + 噪声。"""
    rng = np.random.default_rng(seed)
    x = rng.uniform(-3.0, 3.0, size=(n, 1))
    y = 3.0 * x[:, 0] + 2.0 + rng.normal(0.0, noise, n)
    return x, y


def make_scaled(n: int = 200, seed: int = SEED):
    """两个特征尺度差 1000 倍：x1 ~ N(0,1)、x2 ~ N(0,1000)。"""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0.0, 1.0, n)
    x2 = rng.normal(0.0, 1000.0, n)
    X = np.column_stack([x1, x2])
    y = 2.0 * x1 + 0.003 * x2 + 5.0 + rng.normal(0.0, 0.5, n)
    return X, y


# ---------------------------------------------------------------- 实验一

def experiment_main() -> dict:
    X, y = make_1d()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED)

    t0 = time.perf_counter()
    gd = Model(lr=GD_LR, epochs=GD_EPOCHS, tol=1e-12).fit(X_tr, y_tr)
    t_gd = time.perf_counter() - t0

    cf_w, cf_b = impl.closed_form(X_tr, y_tr)

    lin = framework.fit_linear(X_tr, y_tr)
    sgd = framework.fit_sgd(X_tr, y_tr)

    rows = [
        ("手写 GD", gd, gd.raw_coef, gd.raw_intercept, gd.epochs_run, t_gd),
        ("闭式解（手写）", None, cf_w, cf_b, 1, float("nan")),
        ("sklearn 闭式解", lin, lin.coef_, float(lin.intercept_), 1, float("nan")),
        ("sklearn SGD", sgd, sgd.coef, sgd.intercept, -1, float("nan")),
    ]

    print("== 实验一：同一份数据（y = 3x + 2 + 噪声），四条路线 ==")
    print(f"{'方法':16} | {'训练 MSE':>9} | {'测试 MSE':>9} | {'测试 R²':>8} | "
          f"{'w':>8} | {'b':>7} | {'轮数':>6}")
    print("-" * 92)
    out = {}
    for name, model, w, b, epochs, t in rows:
        pred_tr = model.predict(X_tr) if model is not None else X_tr @ w + b
        pred_te = model.predict(X_te) if model is not None else X_te @ w + b
        m_tr, m_te, r_te = mse(y_tr, pred_tr), mse(y_te, pred_te), r2(y_te, pred_te)
        out[name] = {"train_mse": m_tr, "test_mse": m_te, "r2": r_te,
                     "w": float(np.ravel(w)[0]), "b": float(b),
                     "epochs": epochs, "time": t}
        print(f"{name:16} | {m_tr:9.4f} | {m_te:9.4f} | {r_te:8.4f} | "
              f"{float(np.ravel(w)[0]):8.4f} | {float(b):7.4f} | {epochs:>6}")

    gd_row, cf_row = out["手写 GD"], out["闭式解（手写）"]
    lin_row = out["sklearn 闭式解"]
    assert abs(gd_row["test_mse"] - cf_row["test_mse"]) < 0.01 * cf_row["test_mse"], \
        "手写 GD 的测试 MSE 应与闭式解相差 < 1%"
    assert abs(gd_row["w"] - cf_row["w"]) < 1e-4 and abs(gd_row["b"] - cf_row["b"]) < 1e-4, \
        "手写 GD 的系数应与闭式解一致（不是与真值 3/2 一致：噪声会让样本估计偏离真值）"
    assert abs(lin_row["test_mse"] - cf_row["test_mse"]) < 1e-12, \
        "sklearn 闭式解应与手写闭式解完全一致（同一条数学路线）"
    print("\n→ 手写 GD、闭式解、sklearn 闭式解的测试 MSE 一致；"
          "SGD 略差（随机梯度 + 常数学习率，未调参）。\n")
    return out


# ---------------------------------------------------------------- 实验二

def experiment_learning_rate() -> list:
    X, y = make_1d()
    print("== 实验二：学习率扫描（标准化后的 1 维数据，最多 5000 轮） ==")
    print(f"{'lr':>7} | {'最终训练 MSE':>12} | {'轮数':>5} | 状态")
    print("-" * 48)
    rows = []
    for lr in (0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 1.5):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(over="ignore", invalid="ignore"):
                model = Model(lr=lr, epochs=GD_EPOCHS, tol=1e-12).fit(X, y)
        final = model.loss_history[-1]
        diverged = (not np.isfinite(final)) or final > model.loss_history[0]
        status = "发散/震荡" if diverged else (
            "收敛" if model.epochs_run < GD_EPOCHS else "未完全收敛")
        rows.append({"lr": lr, "mse": final, "epochs": model.epochs_run, "status": status})
        print(f"{lr:7.3f} | {final:12.4f} | {model.epochs_run:5d} | {status}")
    assert any(r["lr"] == 0.001 and r["status"] != "发散" for r in rows)
    assert any(r["lr"] == 1.5 and r["status"].startswith("发散") for r in rows), \
        "学习率过大时应发散（本数据上 lr=1.5 已越过稳定边界）"
    print("\n→ 小 lr 走得慢；越过稳定边界（约 1/L）后 loss 直接爆掉。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_standardize() -> list:
    X, y = make_scaled()
    print("== 实验三：特征尺度差 1000 倍时，标准化救不救 GD（lr=0.01） ==")
    print(f"{'方案':22} | {'最终训练 MSE':>12} | {'轮数':>5} | 说明")
    print("-" * 66)
    rows = []
    for label, standardize in (("先标准化", True), ("不标准化", False)):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(over="ignore", invalid="ignore"):
                model = Model(lr=0.01, epochs=2000, tol=1e-12,
                              standardize=standardize).fit(X, y)
        final = model.loss_history[-1]
        initial = float(np.mean((y - y.mean()) ** 2))
        ok = np.isfinite(final) and final < initial and model.epochs_run < 2000
        rows.append({"label": label, "mse": final, "epochs": model.epochs_run, "ok": ok})
        note = "正常收敛" if ok else "发散 / 未收敛（步长被大尺度特征放大）"
        print(f"{label:22} | {final:12.4f} | {model.epochs_run:5d} | {note}")
    assert rows[0]["ok"] and not rows[1]["ok"], "本数据上标准化应显著改善收敛"
    print("\n→ 同一个 lr：标准化后正常收敛，不标准化直接爆掉——尺度决定步长是否安全。\n")
    return rows


# ---------------------------------------------------------------- 实验四

def _median_time(fn, repeats: int = REPEATS) -> tuple[object, float]:
    times = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


def experiment_timing() -> dict:
    X, y = make_1d()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED)

    gd, t_gd = _median_time(lambda: Model(lr=GD_LR, epochs=GD_EPOCHS, tol=1e-12).fit(X_tr, y_tr))
    (cf_w, cf_b), t_cf = _median_time(lambda: impl.closed_form(X_tr, y_tr))
    lin, t_lin = _median_time(lambda: framework.fit_linear(X_tr, y_tr))

    rows = {
        f"手写 GD（{gd.epochs_run} 轮）": (mse(y_te, gd.predict(X_te)), t_gd),
        "手写闭式解": (mse(y_te, X_te @ cf_w + cf_b), t_cf),
        "sklearn 闭式解": (mse(y_te, lin.predict(X_te)), t_lin),
    }
    print("== 实验四：测试 MSE 与耗时（9 次中位数；毫秒级数字随环境波动） ==")
    print(f"{'方法':20} | {'测试 MSE':>9} | {'中位耗时(ms)':>12}")
    print("-" * 50)
    for name, (m, t) in rows.items():
        print(f"{name:20} | {m:9.4f} | {t * 1000:12.4f}")
    assert max(r[0] for r in rows.values()) - min(r[0] for r in rows.values()) < 0.01
    print("\n→ 精度相同；GD 的代价是几千轮矩阵乘法，闭式解一次分解就结束。\n")
    return {k: {"mse": v[0], "time": v[1]} for k, v in rows.items()}


# ---------------------------------------------------------------- 手算示例

def experiment_hand_calc() -> dict:
    """3 个点、初始化 w=0/b=0、lr=0.1 走一步——与 README「手算示例」逐格对应。"""
    X = np.array([[1.0], [2.0], [3.0]])
    y = np.array([3.0, 5.0, 7.0])
    lr, w, b = 0.1, 0.0, 0.0
    y_hat = X @ np.array([w]) + b
    err = y_hat - y
    grad_w = 2.0 / len(y) * float((X.T @ err).item())
    grad_b = 2.0 / len(y) * float(err.sum())
    w1, b1 = w - lr * grad_w, b - lr * grad_b
    mse0 = float(np.mean(err ** 2))
    mse1 = float(np.mean((X @ np.array([w1]) + b1 - y) ** 2))

    print("== 手算示例：3 个点、一步梯度下降（lr = 0.1） ==")
    print(f"初始：w = {w:.4f}, b = {b:.4f}, 预测 = {np.round(y_hat, 4).tolist()}, "
          f"误差 = {np.round(err, 4).tolist()}, MSE = {mse0:.4f}")
    print(f"梯度：grad_w = {grad_w:.4f}, grad_b = {grad_b:.4f}")
    print(f"一步后：w = {w1:.4f}, b = {b1:.4f}, 预测 = "
          f"{np.round(X @ np.array([w1]) + b1, 4).tolist()}, MSE = {mse1:.4f}")
    assert abs(grad_w + 22.666666666666668) < 1e-9 and abs(grad_b + 10.0) < 1e-9
    assert mse1 < mse0
    print("→ 一步之后 MSE 下降；梯度的符号与大小就是「往哪走、走多远」。\n")
    return {"grad_w": grad_w, "grad_b": grad_b, "w1": w1, "b1": b1,
            "mse0": mse0, "mse1": mse1}


def main() -> None:
    experiment_hand_calc()
    experiment_main()
    experiment_learning_rate()
    experiment_standardize()
    experiment_timing()


if __name__ == "__main__":
    main()
