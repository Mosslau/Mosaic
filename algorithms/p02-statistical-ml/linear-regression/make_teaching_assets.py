"""线性回归与梯度下降 — 图文素材生成器（供 README 引用）。

原则：素材全部由本脚本生成，且与 `impl.py` / `demo.py` 的数字逐项对账——不一致直接报错、
不出图（纪律④）。

产出（`images/` 目录）：
    00-损失地形与下降路径.png   MSE 的等高线 + 手写 GD 的下降轨迹（概念图）
    01-学习率与收敛.png        不同学习率下的 loss 曲线：太慢、刚好、发散
    02-手写vs框架.png          拟合直线 + 三种实现的测试误差对比
    03-梯度下降动画.gif        轨迹在损失地形上一步步走（过程动画）

运行：cd algorithms/p02-statistical-ml/linear-regression && uv run python make_teaching_assets.py
"""

import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)


def setup_cjk_font() -> str:
    """注册一个确实含中文字形的字体；找不到就报错，绝不画方块。"""
    names = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC", "Source Han Sans CN",
             "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
             "Hiragino Sans GB", "PingFang SC", "Heiti TC", "STHeiti", "Songti SC",
             "Arial Unicode MS", "Microsoft YaHei", "SimHei")
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in names if n in available), None)
    if chosen is None:
        raise SystemExit("找不到含中文字形的字体，拒绝生成方块版素材。")
    font_path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font
    if ft2font.FT2Font(font_path).get_char_index(ord("中")) == 0:
        raise SystemExit(f"字体 {chosen} 不含中文字形，拒绝生成方块版素材")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


FONT_USED = setup_cjk_font()

import demo as D  # noqa: E402
import framework  # noqa: E402
import impl  # noqa: E402

COLOR = dict(gd="#2b8a3e", cf="#c92a2a", sgd="#3b5bdb", grid="#dee2e6",
             text="#343a40", path="#f6c344", bad="#e8590c")


# ---------------------------------------------------------------- 取数

def fit_gd(X: np.ndarray, y: np.ndarray, lr: float = D.GD_LR) -> impl.Model:
    return impl.Model(lr=lr, epochs=D.GD_EPOCHS, tol=1e-12).fit(X, y)


def hand_calc() -> dict:
    """与 demo.experiment_hand_calc 完全一致的 3 点一步算例。"""
    X = np.array([[1.0], [2.0], [3.0]])
    y = np.array([3.0, 5.0, 7.0])
    lr, w, b = 0.1, 0.0, 0.0
    err = X @ np.array([w]) + b - y
    grad_w = 2.0 / len(y) * float((X.T @ err).item())
    grad_b = 2.0 / len(y) * float(err.sum())
    return {"grad_w": grad_w, "grad_b": grad_b,
            "w1": w - lr * grad_w, "b1": b - lr * grad_b,
            "mse0": float(np.mean(err ** 2)),
            "mse1": float(np.mean((X @ np.array([w - lr * grad_w]) + (b - lr * grad_b) - y) ** 2))}


def main_data() -> dict:
    X, y = D.make_1d(n=200, seed=D.SEED)
    gd = fit_gd(X, y)
    w_cf, b_cf = impl.closed_form(X, y)
    sgd = framework.fit_sgd(X, y)
    return {"X": X, "y": y, "gd": gd, "cf": (w_cf, b_cf), "sgd": sgd}


# ---------------------------------------------------------------- 对账

def verify(d: dict) -> None:
    hc = hand_calc()
    assert abs(hc["grad_w"] + 22.666666666666668) < 1e-9, hc
    assert abs(hc["grad_b"] + 10.0) < 1e-9, hc
    assert abs(hc["w1"] - 2.266666666666667) < 1e-9, hc
    assert abs(hc["mse1"] - 0.3318518518518518) < 1e-9, hc

    gd, (w_cf, b_cf) = d["gd"], d["cf"]
    mse_gd = impl.mse(d["y"], gd.predict(d["X"]))
    mse_cf = impl.mse(d["y"], d["X"] @ w_cf + b_cf)
    assert abs(mse_gd - mse_cf) < 1e-8, f"GD 与闭式解 MSE 不一致：{mse_gd} vs {mse_cf}"
    assert abs(gd.raw_coef[0] - w_cf[0]) < 1e-5 and abs(gd.raw_intercept - b_cf) < 1e-5, \
        "换回原始尺度后的系数应与闭式解一致"

    losses = np.asarray(gd.loss_history)
    assert np.all(np.diff(losses) <= 1e-12), "GD 的 loss 应当单调不增"
    assert gd.epochs_run < D.GD_EPOCHS, "本数据上 GD 应当提前收敛（否则耗时数字会变）"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with np.errstate(over="ignore", invalid="ignore"):
            z = fit_gd(d["X"], d["y"], lr=1.5)
    final = z.loss_history[-1]
    assert (not np.isfinite(final)) or final > z.loss_history[0], "lr=1.5 应当发散/震荡"
    print(f"  ✓ 对账通过：手算一步 MSE {hc['mse0']:.4f} → {hc['mse1']:.4f}；"
          f"GD {gd.epochs_run} 轮收敛，与闭式解 MSE 一致（{mse_gd:.4f}）；lr=1.5 发散")


# ---------------------------------------------------------------- 图 1：损失地形

def _loss_grid(Xs: np.ndarray, y: np.ndarray, w_grid: np.ndarray,
               b_grid: np.ndarray) -> np.ndarray:
    W, B = np.meshgrid(w_grid, b_grid)
    err = Xs[:, 0, None, None] * W[None, :, :] + B[None, :, :] - y[:, None, None]
    return np.mean(err ** 2, axis=0)


def make_landscape(d: dict) -> None:
    X, y, gd = d["X"], d["y"], d["gd"]
    scale = X.std(axis=0)
    Xs = (X - X.mean(axis=0)) / scale
    w_star, b_star = gd.w[0], gd.b
    # 网格必须同时覆盖起点 (0, ȳ) 与最优点，否则轨迹会画到图外
    w_lo = min(0.0, w_star) - 1.2
    w_hi = max(0.0, w_star) + 1.2
    b0 = float(y.mean())
    b_lo = min(b0, b_star) - 1.5
    b_hi = max(b0, b_star) + 1.5
    w_grid = np.linspace(w_lo, w_hi, 120)
    b_grid = np.linspace(b_lo, b_hi, 120)
    loss = _loss_grid(Xs, y, w_grid, b_grid)

    fig, ax = plt.subplots(figsize=(8.4, 6.4))
    cs = ax.contourf(w_grid, b_grid, loss, levels=30, cmap="viridis", alpha=0.85)
    fig.colorbar(cs, ax=ax, label="MSE")
    path = np.array([(float(np.ravel(w)[0]), float(b)) for w, b in gd.param_history])
    ax.plot(path[:, 0], path[:, 1], "-", color=COLOR["path"], lw=2.4, label="梯度下降轨迹")
    ax.scatter([path[0, 0]], [path[0, 1]], color="white", edgecolor="black", s=70,
               zorder=5, label="起点（w=0，b=标签均值）")
    ax.scatter([w_star], [b_star], marker="*", s=260, color=COLOR["cf"], zorder=6,
               label="收敛到的最优点")
    ax.set_xlabel("w（标准化空间的权重）", fontsize=12)
    ax.set_ylabel("b（偏置）", fontsize=12)
    ax.set_title("MSE 是一张碗：梯度下降从任意起点往碗底走", fontsize=13)
    ax.legend(loc="upper right", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-损失地形与下降路径.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- 图 2：学习率

def make_learning_rate(d: dict) -> dict:
    X, y = d["X"], d["y"]
    lrs = (0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 1.5)
    rows = {}
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    for lr in lrs:
        with np.errstate(over="ignore", invalid="ignore"):
            model = fit_gd(X, y, lr=lr)
        losses = np.asarray(model.loss_history)
        rows[lr] = {"final": float(losses[-1]), "epochs": model.epochs_run}
        ax.plot(np.arange(1, len(losses) + 1), losses, lw=1.9,
                label=f"lr={lr:g}（{model.epochs_run} 轮）")
    ax.set_yscale("log")
    ax.set_xscale("log")
    ax.set_xlabel("迭代轮数（对数轴）", fontsize=12)
    ax.set_ylabel("训练 MSE（对数轴）", fontsize=12)
    ax.grid(True, which="both", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9.5, ncol=2)
    ax.set_title("学习率：太小走不动、太大直接冲出碗外", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-学习率与收敛.png", dpi=130)
    plt.close(fig)
    return rows


# ---------------------------------------------------------------- 图 3：手写 vs 框架

def make_fit_comparison(d: dict) -> dict:
    X, y, gd = d["X"], d["y"], d["gd"]
    w_cf, b_cf = d["cf"]
    sgd = d["sgd"]
    grid = np.linspace(X.min(), X.max(), 50).reshape(-1, 1)

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.2))
    ax = axes[0]
    ax.scatter(X[:, 0], y, s=16, alpha=0.5, color="#868e96", label="数据点")
    ax.plot(grid[:, 0], gd.predict(grid), color=COLOR["gd"], lw=2.6, label="手写 GD")
    ax.plot(grid[:, 0], grid[:, 0] * w_cf[0] + b_cf, "--", color=COLOR["cf"], lw=1.8,
            label="闭式解 / sklearn")
    ax.plot(grid[:, 0], sgd.predict(grid), ":", color=COLOR["sgd"], lw=2.0, label="sklearn SGD")
    ax.set_xlabel("x", fontsize=12)
    ax.set_ylabel("y", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("拟合结果：三条线几乎重合", fontsize=12.5)

    ax = axes[1]
    names = ["手写 GD", "闭式解", "sklearn SGD"]
    preds = [gd.predict(X), X @ w_cf + b_cf, sgd.predict(X)]
    mses = [impl.mse(y, p) for p in preds]
    bars = ax.bar(names, mses, color=[COLOR["gd"], COLOR["cf"], COLOR["sgd"]], width=0.55)
    for bar, m in zip(bars, mses):
        ax.text(bar.get_x() + bar.get_width() / 2, m + 0.01, f"{m:.4f}",
                ha="center", fontsize=11)
    ax.set_ylim(0, max(mses) * 1.25)
    ax.set_ylabel("训练 MSE", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.set_title("三种实现的训练 MSE：GD 与闭式解一致，SGD 略有残差", fontsize=12.5)

    fig.tight_layout()
    fig.savefig(IMAGES / "02-手写vs框架.png", dpi=130)
    plt.close(fig)
    return {"mse_gd": mses[0], "mse_cf": mses[1], "mse_sgd": mses[2]}


# ---------------------------------------------------------------- 图 4：动画

def make_animation(d: dict) -> None:
    X, y, gd = d["X"], d["y"], d["gd"]
    scale = X.std(axis=0)
    Xs = (X - X.mean(axis=0)) / scale
    w_star, b_star = gd.w[0], gd.b
    w_lo = min(0.0, w_star) - 1.2
    w_hi = max(0.0, w_star) + 1.2
    b0 = float(y.mean())
    b_lo = min(b0, b_star) - 1.5
    b_hi = max(b0, b_star) + 1.5
    w_grid = np.linspace(w_lo, w_hi, 110)
    b_grid = np.linspace(b_lo, b_hi, 110)
    loss = _loss_grid(Xs, y, w_grid, b_grid)
    path = np.array([(float(np.ravel(w)[0]), float(b)) for w, b in gd.param_history])
    step = max(1, len(path) // 18)
    frames = list(range(1, len(path) + 1, step))
    if frames[-1] != len(path):
        frames.append(len(path))

    fig, ax = plt.subplots(figsize=(8.0, 6.2))
    ax.contourf(w_grid, b_grid, loss, levels=30, cmap="viridis", alpha=0.85)

    def draw(k: int) -> None:
        ax.clear()
        ax.contourf(w_grid, b_grid, loss, levels=30, cmap="viridis", alpha=0.85)
        ax.plot(path[:k, 0], path[:k, 1], "-", color=COLOR["path"], lw=2.6)
        ax.scatter([path[k - 1, 0]], [path[k - 1, 1]], s=90, color=COLOR["path"],
                   edgecolor="black", zorder=5)
        ax.scatter([w_star], [b_star], marker="*", s=240, color=COLOR["cf"], zorder=6)
        ax.set_xlabel("w", fontsize=11)
        ax.set_ylabel("b", fontsize=11)
        ax.set_title(f"梯度下降：第 {k}/{len(path)} 轮", fontsize=12.5)

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=260)
    anim.save(IMAGES / "03-梯度下降动画.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("取数：一维数据 + 手写 GD + 闭式解 + sklearn …")
    d = main_data()
    print("对账 …")
    verify(d)

    print("① 画损失地形与下降路径 …")
    make_landscape(d)
    print("② 画学习率曲线 …")
    lr_rows = make_learning_rate(d)
    print("③ 画手写 vs 框架 …")
    cmp_rows = make_fit_comparison(d)
    print("④ 画梯度下降动画 …")
    make_animation(d)

    print("\n产出：")
    for name in ("00-损失地形与下降路径.png", "01-学习率与收敛.png",
                 "02-手写vs框架.png", "03-梯度下降动画.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")

    print("\n可粘贴进 README 的手算表：")
    hc = hand_calc()
    print("| 步骤 | 计算 | 数值 |")
    print("|---|---|---|")
    print(f"| 初始 | w=0, b=0，MSE | {hc['mse0']:.4f} |")
    print(f"| 梯度 | grad_w = 2/3·Σxᵢ·errᵢ | {hc['grad_w']:.4f} |")
    print(f"| 梯度 | grad_b = 2/3·Σerrᵢ | {hc['grad_b']:.4f} |")
    print(f"| 更新 | w ← 0 − 0.1·grad_w | {hc['w1']:.4f} |")
    print(f"| 更新 | b ← 0 − 0.1·grad_b | {hc['b1']:.4f} |")
    print(f"| 一步后 | MSE | {hc['mse1']:.4f} |")

    print("\n学习率扫描（最终 MSE / 轮数）：")
    for lr, r in lr_rows.items():
        print(f"  lr={lr:<5g} final={r['final']:.4f}  epochs={r['epochs']}")
    print("\n三种实现训练 MSE：")
    for k, v in cmp_rows.items():
        print(f"  {k} = {v:.6f}")


if __name__ == "__main__":
    main()
