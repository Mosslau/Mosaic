"""逻辑回归 — 图文素材生成器（供 README 引用）。

原则：素材全部由本脚本生成，且与 `impl.py` / `demo.py` 的数字逐项对账——不一致直接报错、
不出图（纪律④）。

产出（`images/` 目录）：
    00-决策边界.png      两类样本 + p=0.5 的边界（以及 p=0.3/0.7 的等高线）
    01-损失与学习率.png  不同学习率下的 BCE 曲线
    02-不平衡与阈值.png  阈值扫描：精确率/召回/F1，以及预测为正的比例
    03-决策边界动画.gif  训练过程中边界如何转动

运行：cd algorithms/p02-statistical-ml/logistic-regression && uv run python make_teaching_assets.py
"""

import os
import sys
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

COLOR = dict(pos="#c92a2a", neg="#3b5bdb", line="#2b8a3e", grid="#dee2e6",
             text="#343a40", hl="#f6c344", bad="#e8590c")


# ---------------------------------------------------------------- 取数

def fit_gd(X, y, lr=D.GD_LR):
    return impl.Model(lr=lr, epochs=D.GD_EPOCHS, tol=1e-12).fit(X, y)


def boundary_line(model: impl.Model, x1_range):
    """把标准化空间的 z=0 换成原始空间的直线 x2 = a·x1 + c。"""
    w = model.w / model._sigma
    b = model.b - model._mu @ w
    a = -w[0] / w[1]
    c = -b / w[1]
    return a * x1_range + c


def level_line(model: impl.Model, x1_range, p: float):
    """z = logit(p) 的等高线。"""
    w = model.w / model._sigma
    b = model.b - model._mu @ w
    logit = np.log(p / (1 - p))
    a = -w[0] / w[1]
    c = (logit - b) / w[1]
    return a * x1_range + c


# ---------------------------------------------------------------- 对账

def verify(d: dict) -> None:
    hc = D.experiment_hand_calc()
    assert abs(hc["grad_w"] + 0.25) < 1e-12 and abs(hc["grad_b"]) < 1e-12
    assert abs(hc["loss0"] - 0.6931) < 1e-4 and abs(hc["loss1"] - 0.6668) < 1e-4

    gd, sk = d["gd"], d["sk"]
    assert np.allclose(gd.raw_coef, sk.coef, atol=0.02), "手写与 sklearn 系数不一致"
    assert abs(gd.raw_intercept - sk.intercept) < 0.02, "截距不一致"
    losses = np.asarray(gd.loss_history)
    assert np.all(np.diff(losses) <= 1e-12), "训练 loss 应单调不增"

    X, y = d["imb_X"], d["imb_y"]
    plain = impl.Model(lr=D.GD_LR, epochs=D.GD_EPOCHS, tol=1e-12).fit(X, y)
    bal = impl.Model(lr=D.GD_LR, epochs=D.GD_EPOCHS, tol=1e-12,
                     class_weight="balanced").fit(X, y)
    r_plain = impl.recall(y, plain.predict(X))
    r_bal = impl.recall(y, bal.predict(X))
    assert r_bal > r_plain, f"重加权应提升召回：{r_bal} vs {r_plain}"

    proba = plain.predict_proba(X)
    p1 = impl.precision(y, (proba >= 0.8).astype(int))
    p2 = impl.precision(y, (proba >= 0.2).astype(int))
    assert p1 > p2, "阈值升高时精确率应上升"
    print(f"  ✓ 对账通过：手算 BCE {hc['loss0']:.4f}→{hc['loss1']:.4f}；"
          f"GD 与 sklearn 系数一致；重加权召回 {r_plain:.3f}→{r_bal:.3f}；"
          f"阈值 0.2→0.8 精确率 {p2:.3f}→{p1:.3f}")


def main_data() -> dict:
    X, y = D.make_blobs()
    gd = fit_gd(X, y)
    sk = framework.fit_logreg(X, y)
    imb_X, imb_y = D.make_imbalanced(n=1200)
    return {"X": X, "y": y, "gd": gd, "sk": sk, "imb_X": imb_X, "imb_y": imb_y}


# ---------------------------------------------------------------- 图 1：决策边界

def make_boundary(d: dict) -> None:
    X, y, gd = d["X"], d["y"], d["gd"]
    fig, ax = plt.subplots(figsize=(8.2, 6.6))
    ax.scatter(X[y == 0, 0], X[y == 0, 1], s=18, alpha=0.55, color=COLOR["neg"], label="类别 0")
    ax.scatter(X[y == 1, 0], X[y == 1, 1], s=18, alpha=0.55, color=COLOR["pos"], label="类别 1")

    xs = np.linspace(X[:, 0].min() - 0.5, X[:, 0].max() + 0.5, 100)
    ax.plot(xs, boundary_line(gd, xs), color=COLOR["line"], lw=2.6, label="p = 0.5（决策边界）")
    ax.plot(xs, level_line(gd, xs, 0.3), "--", color=COLOR["hl"], lw=1.5, label="p = 0.3")
    ax.plot(xs, level_line(gd, xs, 0.7), ":", color=COLOR["hl"], lw=1.8, label="p = 0.7")

    ax.set_xlabel("x1", fontsize=12)
    ax.set_ylabel("x2", fontsize=12)
    ax.set_xlim(X[:, 0].min() - 0.5, X[:, 0].max() + 0.5)
    ax.set_ylim(X[:, 1].min() - 0.5, X[:, 1].max() + 0.5)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, loc="upper left")
    ax.set_title("决策边界是一条直线；两条虚线之间是「不确定区」", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-决策边界.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- 图 2：学习率

def make_learning_rate(d: dict) -> dict:
    X, y = d["X"], d["y"]
    lrs = (0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 30.0)
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    rows = {}
    for lr in lrs:
        with np.errstate(over="ignore", invalid="ignore"):
            model = fit_gd(X, y, lr=lr)
        losses = np.asarray(model.loss_history)
        rows[lr] = {"final": float(losses[-1]), "epochs": model.epochs_run}
        ax.plot(np.arange(1, len(losses) + 1), losses, lw=1.9,
                label=f"lr={lr:g}（{model.epochs_run} 轮）")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("迭代轮数（对数轴）", fontsize=12)
    ax.set_ylabel("训练 BCE（对数轴）", fontsize=12)
    ax.grid(True, which="both", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9.5, ncol=2)
    ax.set_title("学习率：小步慢走、大步震荡；lr=30 已越过稳定边界", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-损失与学习率.png", dpi=130)
    plt.close(fig)
    return rows


# ---------------------------------------------------------------- 图 3：不平衡阈值

def make_threshold(d: dict) -> list:
    X, y = d["imb_X"], d["imb_y"]
    model = impl.Model(lr=D.GD_LR, epochs=D.GD_EPOCHS, tol=1e-12).fit(X, y)
    proba = model.predict_proba(X)
    ths = np.linspace(0.05, 0.95, 37)
    rows = []
    for th in ths:
        pred = (proba >= th).astype(int)
        rows.append({"th": th, "precision": impl.precision(y, pred),
                     "recall": impl.recall(y, pred), "f1": impl.f1(y, pred),
                     "rate": float(pred.mean())})

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.2))
    ax = axes[0]
    ax.plot(ths, [r["precision"] for r in rows], color=COLOR["neg"], lw=2.2, label="精确率")
    ax.plot(ths, [r["recall"] for r in rows], color=COLOR["pos"], lw=2.2, label="召回")
    ax.plot(ths, [r["f1"] for r in rows], color=COLOR["line"], lw=2.2, label="F1")
    ax.axvline(0.5, color=COLOR["text"], ls="--", lw=1.2, label="默认阈值 0.5")
    ax.set_xlabel("阈值", fontsize=12)
    ax.set_ylabel("指标值", fontsize=12)
    ax.set_ylim(0, 1.02)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("阈值升高：精确率↑、召回↓", fontsize=12.5)

    ax = axes[1]
    ax.plot(ths, [r["rate"] for r in rows], color=COLOR["hl"], lw=2.4, label="预测为正的比例")
    ax.axhline(float(y.mean()), color=COLOR["pos"], ls="--", lw=1.6,
               label=f"真实正类比例 {y.mean():.1%}")
    ax.set_xlabel("阈值", fontsize=12)
    ax.set_ylabel("比例", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("阈值就是「打算判多少人为正」", fontsize=12.5)

    fig.tight_layout()
    fig.savefig(IMAGES / "02-不平衡与阈值.png", dpi=130)
    plt.close(fig)
    return rows


# ---------------------------------------------------------------- 图 4：动画

def make_animation(d: dict) -> None:
    X, y, gd = d["X"], d["y"], d["gd"]
    path = [(float(w[0]), float(w[1]), float(b)) for w, b in gd.param_history]
    step = max(1, len(path) // 20)
    frames = list(range(0, len(path), step))
    if frames[-1] != len(path) - 1:
        frames.append(len(path) - 1)

    fig, ax = plt.subplots(figsize=(7.6, 6.2))

    def draw(k: int) -> None:
        ax.clear()
        ax.scatter(X[y == 0, 0], X[y == 0, 1], s=14, alpha=0.5, color=COLOR["neg"])
        ax.scatter(X[y == 1, 0], X[y == 1, 1], s=14, alpha=0.5, color=COLOR["pos"])
        w0, w1, b = path[k]
        # 用路径里的参数还原原始尺度直线
        mu, sigma = gd._mu, gd._sigma
        wr = np.array([w0, w1]) / sigma
        br = b - mu @ wr
        xs = np.linspace(X[:, 0].min() - 0.5, X[:, 0].max() + 0.5, 100)
        ax.plot(xs, -(wr[0] * xs + br) / wr[1], color=COLOR["line"], lw=2.6)
        ax.set_xlim(X[:, 0].min() - 0.5, X[:, 0].max() + 0.5)
        ax.set_ylim(X[:, 1].min() - 0.5, X[:, 1].max() + 0.5)
        ax.set_xlabel("x1", fontsize=11)
        ax.set_ylabel("x2", fontsize=11)
        ax.set_title(f"训练第 {k + 1}/{len(path)} 轮：边界在转动", fontsize=12.5)

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=300)
    anim.save(IMAGES / "03-决策边界动画.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("取数：二维数据 + 手写 GD + sklearn + 不平衡数据 …")
    d = main_data()
    print("对账 …")
    verify(d)
    print("① 画决策边界 …")
    make_boundary(d)
    print("② 画学习率曲线 …")
    lr_rows = make_learning_rate(d)
    print("③ 画不平衡阈值 …")
    th_rows = make_threshold(d)
    print("④ 画训练动画 …")
    make_animation(d)

    print("\n产出：")
    for name in ("00-决策边界.png", "01-损失与学习率.png",
                 "02-不平衡与阈值.png", "03-决策边界动画.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")

    print("\n学习率扫描（最终 BCE / 轮数）：")
    for lr, r in lr_rows.items():
        print(f"  lr={lr:<5g} final={r['final']:.4f}  epochs={r['epochs']}")
    print("\n阈值扫描抽样（precision / recall）：")
    for r in th_rows[::6]:
        print(f"  th={r['th']:.2f}  p={r['precision']:.3f}  r={r['recall']:.3f}  "
              f"正类比例={r['rate']:.3f}")


if __name__ == "__main__":
    main()
