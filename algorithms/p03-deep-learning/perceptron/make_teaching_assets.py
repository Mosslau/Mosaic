"""感知机 — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-边界对比.png      感知机 vs 逻辑回归的决策边界
    01-收敛与震荡.png    线性可分 vs XOR 的每轮错误数
    02-顺序敏感.png      10 个随机种子得到的不同边界
    03-边界生长.gif      训练过程中感知机边界的移动
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

COLOR = dict(pos="#c92a2a", neg="#3b5bdb", line="#2b8a3e", alt="#f08c00",
             grid="#dee2e6", hl="#f6c344", text="#343a40")


def raw_line(model: impl.Perceptron):
    w = model.raw_coef
    b = model.b - model._mu @ w
    return w, b


def draw_line(ax, w, b, color, label, ls="-"):
    xs = np.linspace(-4, 4, 200)
    if abs(w[1]) > 1e-12:
        ys = -(w[0] * xs + b) / w[1]
        ax.plot(xs, ys, ls, color=color, lw=2, label=label)


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.make_separable()
    hand = impl.Perceptron(lr=0.1, epochs=50, random_state=0).fit(X_tr, y_tr)
    assert np.mean(hand.predict(X_te) == y_te) == 1.0
    assert hand.errors_per_epoch[-1] == 0
    X, y = D.make_xor()
    bad = impl.Perceptron(lr=0.1, epochs=50, random_state=0).fit(X, y)
    assert bad.errors_per_epoch[-1] > 0
    print(f"  ✓ 对账通过：可分数据 100%，XOR 最后一轮 {bad.errors_per_epoch[-1]} 个错误")


def make_boundary() -> None:
    X_tr, X_te, y_tr, y_te = D.make_separable()
    hand = impl.Perceptron(lr=0.1, epochs=50, random_state=0).fit(X_tr, y_tr)
    log = framework.fit_logistic(X_tr, y_tr)
    fig, ax = plt.subplots(figsize=(8.0, 6.2))
    ax.scatter(X_te[y_te == -1, 0], X_te[y_te == -1, 1], s=18, color=COLOR["neg"], label="类 -1")
    ax.scatter(X_te[y_te == 1, 0], X_te[y_te == 1, 1], s=18, color=COLOR["pos"], label="类 +1")
    w, b = raw_line(hand)
    draw_line(ax, w, b, COLOR["line"], "感知机边界")
    draw_line(ax, log.coef_[0], log.intercept_[0], COLOR["alt"], "逻辑回归边界", "--")
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(-3.5, 3.5)
    ax.set_xlabel("x0")
    ax.set_ylabel("x1")
    ax.grid(True, color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9, loc="upper left")
    ax.set_title("都分对，但停在不同边界：感知机不最大化间隔", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-边界对比.png", dpi=130)
    plt.close(fig)


def make_errors() -> None:
    X_tr, _, y_tr, _ = D.make_separable()
    X_x, y_x = D.make_xor()
    good = impl.Perceptron(lr=0.1, epochs=15, random_state=0).fit(X_tr, y_tr)
    bad = impl.Perceptron(lr=0.1, epochs=15, random_state=0).fit(X_x, y_x)
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.plot(range(1, len(good.errors_per_epoch) + 1), good.errors_per_epoch,
            "o-", color=COLOR["line"], lw=2, label="线性可分")
    ax.plot(range(1, len(bad.errors_per_epoch) + 1), bad.errors_per_epoch,
            "s--", color=COLOR["pos"], lw=2, label="XOR（不可分）")
    ax.set_xlabel("epoch", fontsize=12)
    ax.set_ylabel("本轮错误数", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("可分：错误数归零；不可分：上下震荡、不收敛", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-收敛与震荡.png", dpi=130)
    plt.close(fig)


def make_seeds() -> None:
    X_tr, X_te, y_tr, y_te = D.make_separable()
    fig, ax = plt.subplots(figsize=(8.0, 6.2))
    ax.scatter(X_te[y_te == -1, 0], X_te[y_te == -1, 1], s=14, color=COLOR["neg"], alpha=0.5)
    ax.scatter(X_te[y_te == 1, 0], X_te[y_te == 1, 1], s=14, color=COLOR["pos"], alpha=0.5)
    for seed in range(10):
        m = impl.Perceptron(lr=0.1, epochs=50, random_state=seed).fit(X_tr, y_tr)
        w, b = raw_line(m)
        draw_line(ax, w, b, COLOR["line"], "" if seed else "10 个种子的边界", ls="-")
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(-3.5, 3.5)
    ax.set_xlabel("x0")
    ax.set_ylabel("x1")
    ax.grid(True, color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("同一数据、不同样本顺序 → 不同分隔超平面", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-顺序敏感.png", dpi=130)
    plt.close(fig)


def make_animation() -> None:
    X_tr, y_tr = D.make_xor()
    model = impl.Perceptron(lr=0.1, epochs=20, random_state=0).fit(X_tr, y_tr)
    fig, ax = plt.subplots(figsize=(7.0, 6.0))

    def draw(k: int) -> None:
        ax.clear()
        w_s, b_s = model.param_history[k]
        sigma = model._sigma
        w = w_s / sigma
        b = b_s - model._mu @ w
        ax.scatter(X_tr[y_tr == -1, 0], X_tr[y_tr == -1, 1], s=12, color=COLOR["neg"], alpha=0.6)
        ax.scatter(X_tr[y_tr == 1, 0], X_tr[y_tr == 1, 1], s=12, color=COLOR["pos"], alpha=0.6)
        draw_line(ax, w, b, COLOR["line"], "")
        ax.set_xlim(-3.5, 3.5)
        ax.set_ylim(-3.5, 3.5)
        ax.set_title(f"XOR：第 {k + 1} 轮（错误 {model.errors_per_epoch[k]}）", fontsize=12)
        ax.set_xlabel("x0")
        ax.set_ylabel("x1")

    anim = animation.FuncAnimation(fig, draw, frames=len(model.param_history), interval=700)
    anim.save(IMAGES / "03-边界生长.gif", writer=animation.PillowWriter(fps=1.4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画边界对比 …")
    make_boundary()
    print("② 画收敛/震荡 …")
    make_errors()
    print("③ 画顺序敏感 …")
    make_seeds()
    print("④ 画边界生长 …")
    make_animation()
    print("\n产出：")
    for name in ("00-边界对比.png", "01-收敛与震荡.png", "02-顺序敏感.png", "03-边界生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
