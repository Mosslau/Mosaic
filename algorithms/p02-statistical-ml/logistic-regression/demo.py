"""逻辑回归 — demo：同数据双跑 + 四组实验

    uv run python demo.py

产出：
    手算示例      2 个点、一步梯度下降（与 README 逐格对应）
    实验一        二维数据：手写 GD vs sklearn，指标与系数
    实验二        学习率扫描：收敛速度与发散边界
    实验三        类别不平衡：accuracy 陷阱 + 阈值扫描 + 重加权
    实验四        耗时：手写 GD vs sklearn 的 lbfgs
"""

from __future__ import annotations

import statistics
import time
import warnings

import framework
import impl
import numpy as np
from impl import Model, accuracy, f1, precision, recall, roc_auc
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 7
GD_LR = 0.5
GD_EPOCHS = 8000


# ---------------------------------------------------------------- 数据

def make_blobs(n: int = 500, seed: int = SEED):
    """两个有重叠的高斯团：不做特征工程时准确率上不到 100%。"""
    rng = np.random.default_rng(seed)
    n0 = n // 2
    X0 = rng.normal([-1.0, -0.5], 1.0, size=(n0, 2))
    X1 = rng.normal([1.0, 0.5], 1.0, size=(n - n0, 2))
    X = np.vstack([X0, X1])
    y = np.array([0] * n0 + [1] * (n - n0))
    idx = rng.permutation(n)
    return X[idx], y[idx]


def make_imbalanced(n: int = 3000, pos_rate: float = 0.08, seed: int = 2):
    """少数类只占 8%：默认阈值 0.5 会把它几乎全判成多数类。"""
    rng = np.random.default_rng(seed)
    n1 = int(n * pos_rate)
    n0 = n - n1
    X0 = rng.normal([-0.8, 0.0], 1.0, size=(n0, 2))
    X1 = rng.normal([1.0, 0.3], 0.9, size=(n1, 2))
    X = np.vstack([X0, X1])
    y = np.array([0] * n0 + [1] * n1)
    idx = rng.permutation(n)
    return X[idx], y[idx]


def metrics(y_true, proba, threshold: float = 0.5) -> dict:
    pred = (proba >= threshold).astype(int)
    return {
        "accuracy": accuracy(y_true, pred),
        "precision": precision(y_true, pred),
        "recall": recall(y_true, pred),
        "f1": f1(y_true, pred),
        "auc": roc_auc(y_true, proba),
    }


# ---------------------------------------------------------------- 手算示例

def experiment_hand_calc() -> dict:
    """2 个点、w=b=0、lr=0.5 走一步。"""
    X = np.array([[1.0], [2.0]])
    y = np.array([0.0, 1.0])
    lr, w, b = 0.5, 0.0, 0.0
    z = X @ np.array([w]) + b
    p = impl.sigmoid(z)
    loss0 = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    grad_w = float(np.mean((p - y) * X[:, 0]))
    grad_b = float(np.mean(p - y))
    w1, b1 = w - lr * grad_w, b - lr * grad_b
    z1 = X @ np.array([w1]) + b1
    p1 = impl.sigmoid(z1)
    loss1 = float(-np.mean(y * np.log(p1) + (1 - y) * np.log(1 - p1)))

    print("== 手算示例：2 个点、一步梯度下降（lr = 0.5） ==")
    print(f"初始：z = {np.round(z, 4).tolist()}，p = {np.round(p, 4).tolist()}，BCE = {loss0:.4f}")
    print(f"梯度：grad_w = {grad_w:.4f}，grad_b = {grad_b:.4f}")
    print(f"一步后：w = {w1:.4f}，b = {b1:.4f}，p = {np.round(p1, 4).tolist()}，"
          f"BCE = {loss1:.4f}")
    assert abs(grad_w + 0.25) < 1e-12 and abs(grad_b) < 1e-12
    assert abs(loss0 - 0.6931) < 1e-4 and abs(loss1 - 0.6668) < 1e-4
    print("→ 一步之后 BCE 下降；梯度里没有 sigmoid 的导数项，这就是交叉熵的‘巧合’。\n")
    return {"grad_w": grad_w, "grad_b": grad_b, "loss0": loss0, "loss1": loss1}


# ---------------------------------------------------------------- 实验一

def experiment_main() -> dict:
    X, y = make_blobs()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED,
                                              stratify=y)
    gd = Model(lr=GD_LR, epochs=GD_EPOCHS, tol=1e-12).fit(X_tr, y_tr)
    sk = framework.fit_logreg(X_tr, y_tr)

    rows = [
        ("手写 GD", gd, gd.predict_proba(X_te)),
        ("sklearn", sk, sk.predict_proba(X_te)),
    ]
    print("== 实验一：二维重叠数据上的手写 vs sklearn ==")
    print(f"{'方法':10} | {'accuracy':>8} | {'precision':>9} | {'recall':>6} | "
          f"{'f1':>5} | {'auc':>5} | {'轮数':>5}")
    print("-" * 70)
    out = {}
    for name, model, proba in rows:
        m = metrics(y_te, proba)
        out[name] = m
        epochs = getattr(model, "epochs_run", -1)
        print(f"{name:10} | {m['accuracy']:8.4f} | {m['precision']:9.4f} | "
              f"{m['recall']:6.4f} | {m['f1']:5.4f} | {m['auc']:5.4f} | {epochs:>5}")

    print("\n系数对照（换回原始尺度）：")
    print(f"  手写   w = {np.round(gd.raw_coef, 4).tolist()}，b = {gd.raw_intercept:.4f}")
    print(f"  sklearn w = {np.round(sk.coef, 4).tolist()}，b = {sk.intercept:.4f}")

    assert abs(out["手写 GD"]["accuracy"] - out["sklearn"]["accuracy"]) < 0.02, \
        "手写 GD 与 sklearn 的准确率应接近"
    assert abs(out["手写 GD"]["auc"] - out["sklearn"]["auc"]) < 0.02, "AUC 应接近"
    assert np.allclose(gd.raw_coef, sk.coef, atol=0.15), "系数应接近（同一目标函数）"
    print("\n→ 两条路线的分类指标在 2% 内一致；lbfgs 收敛更快但每步更贵。\n")
    return {"rows": out, "gd_epochs": gd.epochs_run, "coef_gd": gd.raw_coef,
            "coef_sk": sk.coef}


# ---------------------------------------------------------------- 实验二

def experiment_learning_rate() -> list:
    X, y = make_blobs()
    print("== 实验二：学习率扫描（标准化后的二维数据，最多 8000 轮） ==")
    print(f"{'lr':>6} | {'最终 BCE':>10} | {'轮数':>5} | 状态")
    print("-" * 42)
    rows = []
    for lr in (0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 30.0):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(over="ignore", invalid="ignore"):
                model = Model(lr=lr, epochs=GD_EPOCHS, tol=1e-12).fit(X, y)
        final = model.loss_history[-1]
        best = min(model.loss_history)
        diverged = (not np.isfinite(final)) or final > 1.2 * best
        status = "发散/震荡" if diverged else (
            "收敛" if model.epochs_run < GD_EPOCHS else "未完全收敛")
        rows.append({"lr": lr, "loss": final, "epochs": model.epochs_run, "status": status})
        print(f"{lr:6.3f} | {final:10.4f} | {model.epochs_run:5d} | {status}")
    assert any(r["lr"] == 0.001 and r["status"] != "发散/震荡" for r in rows)
    assert any(r["lr"] == 30.0 and r["status"] == "发散/震荡" for r in rows), \
        "学习率过大时应震荡/发散"
    print("\n→ 逻辑回归的损失是光滑凸函数；步长超过稳定上界照样会炸。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_imbalance() -> dict:
    X, y = make_imbalanced()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED,
                                              stratify=y)
    print(f"== 实验三：类别不平衡（训练集少数类占比 {y_tr.mean():.1%}） ==")
    print(f"{'方案':22} | {'accuracy':>8} | {'precision':>9} | {'recall':>6} | {'f1':>6}")
    print("-" * 62)
    out = {}
    for label, kwargs in (("默认（阈值 0.5）", {}),
                          ("class_weight=balanced", {"class_weight": "balanced"})):
        model = Model(lr=GD_LR, epochs=GD_EPOCHS, tol=1e-12, **kwargs).fit(X_tr, y_tr)
        proba = model.predict_proba(X_te)
        m = metrics(y_te, proba)
        out[label] = m
        print(f"{label:22} | {m['accuracy']:8.4f} | {m['precision']:9.4f} | "
              f"{m['recall']:6.4f} | {m['f1']:6.4f}")

    default = Model(lr=GD_LR, epochs=GD_EPOCHS, tol=1e-12).fit(X_tr, y_tr)
    proba = default.predict_proba(X_te)
    print("\n阈值扫描（默认模型）：")
    print(f"{'threshold':>9} | {'precision':>9} | {'recall':>6} | "
          f"{'f1':>6} | {'预测为正的比例':>12}")
    print("-" * 60)
    sweep = []
    for th in (0.1, 0.2, 0.3, 0.4, 0.5, 0.7):
        m = metrics(y_te, proba, threshold=th)
        sweep.append({"threshold": th, **m, "positive_rate": float((proba >= th).mean())})
        print(f"{th:9.1f} | {m['precision']:9.4f} | {m['recall']:6.4f} | "
              f"{m['f1']:6.4f} | {float((proba >= th).mean()):12.2%}")

    assert out["默认（阈值 0.5）"]["accuracy"] > 0.85, "不平衡数据上 accuracy 会很高"
    assert out["默认（阈值 0.5）"]["recall"] < 0.5, "但少数类召回很低——这就是 accuracy 陷阱"
    assert out["class_weight=balanced"]["recall"] > out["默认（阈值 0.5）"]["recall"], \
        "重加权应提升少数类召回"
    assert sweep[0]["recall"] > sweep[-1]["recall"], "阈值降低应提升召回"
    print("\n→ accuracy 高不代表模型有用；少数类召回、AUC、业务阈值才是判据。\n")
    return {"models": out, "sweep": sweep}


# ---------------------------------------------------------------- 实验四

def _median_time(fn, repeats: int = REPEATS):
    times = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


def experiment_timing() -> dict:
    X, y = make_blobs()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED,
                                              stratify=y)
    gd, t_gd = _median_time(lambda: Model(lr=GD_LR, epochs=GD_EPOCHS, tol=1e-12).fit(X_tr, y_tr))
    sk, t_sk = _median_time(lambda: framework.fit_logreg(X_tr, y_tr))

    rows = {
        f"手写 GD（{gd.epochs_run} 轮）": (metrics(y_te, gd.predict_proba(X_te))["accuracy"], t_gd),
        "sklearn lbfgs": (metrics(y_te, sk.predict_proba(X_te))["accuracy"], t_sk),
    }
    print("== 实验四：准确率与耗时（7 次中位数；毫秒级数字随环境波动） ==")
    print(f"{'方法':24} | {'accuracy':>8} | {'中位耗时(ms)':>12}")
    print("-" * 52)
    for name, (acc, t) in rows.items():
        print(f"{name:24} | {acc:8.4f} | {t * 1000:12.4f}")
    assert abs(rows[f"手写 GD（{gd.epochs_run} 轮）"][0] - rows["sklearn lbfgs"][0]) < 0.02
    print("\n→ 精度相同；手写 GD 用几百到几千轮矩阵乘法，lbfgs 用二阶信息、每步更贵。\n")
    return {k: {"accuracy": v[0], "time": v[1]} for k, v in rows.items()}


def main() -> None:
    experiment_hand_calc()
    experiment_main()
    experiment_learning_rate()
    experiment_imbalance()
    experiment_timing()


if __name__ == "__main__":
    main()
