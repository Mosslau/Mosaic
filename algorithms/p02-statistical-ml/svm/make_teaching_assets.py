"""支持向量机 SVM — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-最大间隔与支持向量.png  决策边界、两条间隔线、被圈出的支持向量
    01-C与间隔.png             C 扫描：间隔宽度与支持向量数
    02-核技巧.png              同心圆上线性核 vs RBF 核的决策区域
    03-决策边界动画.gif        LinearSVM 训练过程中边界如何转动

运行：cd algorithms/p02-statistical-ml/svm && uv run python make_teaching_assets.py
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
from sklearn.model_selection import train_test_split

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

COLOR = dict(pos="#c92a2a", neg="#3b5bdb", line="#2b8a3e", margin="#f6c344",
             grid="#dee2e6", text="#343a40", sv="#e8590c")


def fit_linear(C: float = 1.0):
    X, y = D.make_blobs()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
    model = impl.KernelSVM(C=C, kernel="linear", max_iter=100, tol=1e-4,
                           standardize=False).fit(X_tr, y_tr)
    return X_tr, y_tr, model


def raw_line(model, x1):
    """把标准化空间的 w·x + b = 常数 换成原始空间的直线。"""
    w = model.coef_ / model._sigma
    b = model.b - model._mu @ w
    return -(w[0] * x1 + b) / w[1]


def verify() -> None:
    X, y = D.make_blobs()
    lin = impl.KernelSVM(C=1.0, kernel="linear", max_iter=100, tol=1e-4,
                         standardize=False).fit(X, y)
    sk = framework.fit_svc(X, y, C=1.0, kernel="linear")
    assert abs(lin.margin - 2.0 / np.linalg.norm(sk.coef_[0])) < 0.05, "线性核间隔与 sklearn 不一致"
    assert lin.n_support == int(sk.n_support_.sum()), "支持向量数与 sklearn 不一致"

    Xc, yc = D.make_circles()
    rbf = impl.KernelSVM(C=10.0, kernel="rbf", max_iter=100, tol=1e-4,
                         standardize=False).fit(Xc, yc)
    assert np.mean(rbf.predict(Xc) == yc) >= 0.95, "RBF 应能分开同心圆"
    print(f"  ✓ 对账通过：线性核间隔 {lin.margin:.3f}（sklearn 同）、SV {lin.n_support}；"
          f"RBF 同心圆准确率 {np.mean(rbf.predict(Xc) == yc):.3f}")


def make_margin_figure() -> None:
    X, y, model = fit_linear()
    xs = np.linspace(X[:, 0].min() - 0.5, X[:, 0].max() + 0.5, 100)
    fig, ax = plt.subplots(figsize=(8.2, 6.6))
    ax.scatter(X[y == -1, 0], X[y == -1, 1], s=18, alpha=0.55, color=COLOR["neg"], label="类别 −1")
    ax.scatter(X[y == 1, 0], X[y == 1, 1], s=18, alpha=0.55, color=COLOR["pos"], label="类别 +1")
    ax.plot(xs, raw_line(model, xs), color=COLOR["line"], lw=2.6, label="w·x + b = 0")
    for c, style, label in ((1.0, "--", "间隔边界 w·x+b = ±1"),
                            (-1.0, "--", None)):
        w = model.coef_ / model._sigma
        b = (model.b - model._mu @ w) + c
        ax.plot(xs, -(w[0] * xs + b) / w[1], style, color=COLOR["margin"], lw=1.8, label=label)
    sv = model.support_
    ax.scatter(X[sv, 0], X[sv, 1], s=160, facecolors="none", edgecolors=COLOR["sv"],
               linewidths=1.8, label=f"支持向量（{len(sv)} 个）")
    ax.set_xlabel("x1", fontsize=12)
    ax.set_ylabel("x2", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9.5, loc="upper left")
    ax.set_title("最大间隔：两条虚线之间的距离由支持向量决定", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-最大间隔与支持向量.png", dpi=130)
    plt.close(fig)


def make_c_figure() -> None:
    X, y = D.make_blobs()
    X_tr, _, y_tr, _ = train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
    Cs = np.array([0.01, 0.1, 1.0, 10.0, 100.0])
    margins, svs = [], []
    for C in Cs:
        m = impl.KernelSVM(C=float(C), kernel="linear", max_iter=150, tol=1e-4,
                              standardize=False).fit(X_tr, y_tr)
        margins.append(m.margin)
        svs.append(m.n_support)
    fig, ax1 = plt.subplots(figsize=(9.4, 5.6))
    ax1.plot(Cs, margins, "o-", color=COLOR["line"], lw=2.2, label="间隔 2/‖w‖")
    ax1.set_xscale("log")
    ax1.set_xlabel("C（对数轴）", fontsize=12)
    ax1.set_ylabel("间隔宽度", fontsize=12, color=COLOR["line"])
    ax2 = ax1.twinx()
    ax2.plot(Cs, svs, "s--", color=COLOR["sv"], lw=1.8, label="支持向量数")
    ax2.set_ylabel("支持向量数", fontsize=12, color=COLOR["sv"])
    ax1.grid(True, color=COLOR["grid"], lw=0.7)
    ax1.set_axisbelow(True)
    ax1.set_title("C 越大，间隔越窄、支持向量越少（更贴训练集）", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-C与间隔.png", dpi=130)
    plt.close(fig)


def make_kernel_figure() -> None:
    X, y = D.make_circles()
    lin = impl.KernelSVM(C=10.0, kernel="linear", max_iter=100, tol=1e-4,
                          standardize=False).fit(X, y)
    rbf = impl.KernelSVM(C=10.0, kernel="rbf", max_iter=100, tol=1e-4,
                          standardize=False).fit(X, y)
    xx, yy = np.meshgrid(np.linspace(X[:, 0].min() - 0.2, X[:, 0].max() + 0.2, 200),
                         np.linspace(X[:, 1].min() - 0.2, X[:, 1].max() + 0.2, 200))
    grid = np.c_[xx.ravel(), yy.ravel()]

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.8))
    for ax, model, title in ((axes[0], lin, "线性核：只能切一条直线"),
                             (axes[1], rbf, "RBF 核：把圆环分开")):
        z = model.decision_function(grid).reshape(xx.shape)
        ax.contourf(xx, yy, z, levels=[-1e9, 0, 1e9], colors=["#dbe4ff", "#ffe3e3"], alpha=0.7)
        ax.contour(xx, yy, z, levels=[-1, 0, 1],
                   colors=[COLOR["margin"], COLOR["line"], COLOR["margin"]],
                   linestyles=["--", "-", "--"], linewidths=[1.3, 2.2, 1.3])
        ax.scatter(X[y == -1, 0], X[y == -1, 1], s=14, color=COLOR["neg"], alpha=0.7)
        ax.scatter(X[y == 1, 0], X[y == 1, 1], s=14, color=COLOR["pos"], alpha=0.7)
        ax.set_title(title, fontsize=12.5)
        ax.set_xlabel("x1")
        ax.set_ylabel("x2")
        ax.set_xticks([])
        ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(IMAGES / "02-核技巧.png", dpi=130)
    plt.close(fig)


def make_animation() -> None:
    X, y = D.make_blobs()
    model = impl.LinearSVM(C=1.0, lr=1e-3, epochs=4000, tol=1e-8).fit(X, y)
    path = [(float(w[0]), float(w[1]), float(b)) for w, b in model.param_history]
    step = max(1, len(path) // 15)
    frames = list(range(0, len(path), step))
    if frames[-1] != len(path) - 1:
        frames.append(len(path) - 1)

    fig, ax = plt.subplots(figsize=(7.6, 6.2))

    def draw(k: int) -> None:
        ax.clear()
        ax.scatter(X[y == -1, 0], X[y == -1, 1], s=14, color=COLOR["neg"], alpha=0.6)
        ax.scatter(X[y == 1, 0], X[y == 1, 1], s=14, color=COLOR["pos"], alpha=0.6)
        w0, w1, b = path[k]
        w = np.array([w0, w1]) / model._sigma
        br = b - model._mu @ w
        xs = np.linspace(X[:, 0].min() - 0.5, X[:, 0].max() + 0.5, 100)
        ax.plot(xs, -(w[0] * xs + br) / w[1], color=COLOR["line"], lw=2.6)
        ax.set_xlim(X[:, 0].min() - 0.5, X[:, 0].max() + 0.5)
        ax.set_ylim(X[:, 1].min() - 0.5, X[:, 1].max() + 0.5)
        ax.set_xlabel("x1", fontsize=11)
        ax.set_ylabel("x2", fontsize=11)
        ax.set_title(f"SVM 训练第 {k + 1}/{len(path)} 轮", fontsize=12.5)

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=260)
    anim.save(IMAGES / "03-决策边界动画.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画最大间隔与支持向量 …")
    make_margin_figure()
    print("② 画 C 与间隔 …")
    make_c_figure()
    print("③ 画核技巧 …")
    make_kernel_figure()
    print("④ 画训练动画 …")
    make_animation()
    print("\n产出：")
    for name in ("00-最大间隔与支持向量.png", "01-C与间隔.png", "02-核技巧.png",
                 "03-决策边界动画.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
