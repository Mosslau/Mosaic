"""随机森林 — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-单树与森林边界.png  单棵树 vs 100 棵树的决策区域
    01-树数与OOB.png       测试准确率与 OOB 随树数的变化
    02-特征重要性.png      真特征（x0–x3）vs 噪声特征
    03-森林投票.gif        逐棵加入树时边界的平滑过程

运行：cd algorithms/p02-statistical-ml/random-forest && uv run python make_teaching_assets.py
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

COLOR = dict(pos="#c92a2a", neg="#3b5bdb", forest="#2b8a3e", oob="#e8590c",
             grid="#dee2e6", hl="#f6c344", text="#343a40")


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.make_moons_data()
    single = impl.RandomForest(n_trees=1, max_features=None, random_state=0).fit(X_tr, y_tr)
    forest = impl.RandomForest(n_trees=100, random_state=0).fit(X_tr, y_tr)
    assert forest.oob_score_ > single.oob_score_, "森林 OOB 应优于单树"
    assert D.accuracy(y_te, forest.predict(X_te)) >= D.accuracy(y_te, single.predict(X_te)) - 0.01

    X_tr2, _, y_tr2, _ = D.make_high_dim()
    hi = impl.RandomForest(n_trees=100, random_state=0).fit(X_tr2, y_tr2)
    order = np.argsort(-hi.feature_importances_)
    assert set(order[:4].tolist()) == {0, 1, 2, 3}, "重要性前 4 应正好是真特征"
    print(f"  ✓ 对账通过：单树 OOB {single.oob_score_:.3f} → 森林 {forest.oob_score_:.3f}；"
          f"重要性前 4 = 真特征；森林测试 acc {D.accuracy(y_te, forest.predict(X_te)):.3f}")


def _grid(X, pad=0.35):
    xx, yy = np.meshgrid(np.linspace(X[:, 0].min() - pad, X[:, 0].max() + pad, 220),
                         np.linspace(X[:, 1].min() - pad, X[:, 1].max() + pad, 220))
    return np.c_[xx.ravel(), yy.ravel()], xx, yy


def _proba(model, grid, k=None):
    trees = model.trees if k is None else model.trees[:k]
    p = np.zeros(len(grid))
    for t in trees:
        p += t.predict_proba(grid)[:, 1]
    return p / len(trees)


def make_boundary() -> None:
    X_tr, X_te, y_tr, y_te = D.make_moons_data()
    single = impl.RandomForest(n_trees=1, max_features=None, random_state=0).fit(X_tr, y_tr)
    forest = impl.RandomForest(n_trees=100, random_state=0).fit(X_tr, y_tr)
    grid, xx, yy = _grid(X_tr)

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.9))
    for ax, model, title in ((axes[0], single, "单棵树（n_trees=1）"),
                             (axes[1], forest, "随机森林（100 棵）")):
        p = _proba(model, grid).reshape(xx.shape)
        ax.contourf(xx, yy, p, levels=[0, 0.5, 1], colors=["#dbe4ff", "#ffe3e3"], alpha=0.85)
        ax.contour(xx, yy, p, levels=[0.5], colors=[COLOR["forest"]], linewidths=2)
        ax.scatter(X_tr[y_tr == 0, 0], X_tr[y_tr == 0, 1], s=13, color=COLOR["neg"],
                   alpha=0.8, label="类别 0")
        ax.scatter(X_tr[y_tr == 1, 0], X_tr[y_tr == 1, 1], s=13, color=COLOR["pos"],
                   alpha=0.8, label="类别 1")
        acc = D.accuracy(y_te, model.predict(X_te))
        ax.set_title(f"{title}（测试 acc {acc:.2f}）", fontsize=12.5)
        ax.set_xlabel("x0")
        ax.set_ylabel("x1")
    axes[0].legend(fontsize=9, loc="upper right")
    fig.tight_layout()
    fig.savefig(IMAGES / "00-单树与森林边界.png", dpi=130)
    plt.close(fig)


def make_n_trees() -> None:
    X_tr, X_te, y_tr, y_te = D.make_moons_data()
    ns = [1, 5, 10, 25, 50, 100, 200]
    test, oob = [], []
    for n in ns:
        m = impl.RandomForest(n_trees=n, random_state=0).fit(X_tr, y_tr)
        test.append(D.accuracy(y_te, m.predict(X_te)))
        oob.append(float(m.oob_score_))
    fig, ax = plt.subplots(figsize=(9.4, 5.4))
    ax.plot(ns, test, "o-", color=COLOR["forest"], lw=2, label="测试准确率")
    ax.plot(ns, oob, "s--", color=COLOR["oob"], lw=1.8, label="OOB 准确率")
    ax.set_xscale("log")
    ax.set_xlabel("n_trees（对数轴）", fontsize=12)
    ax.set_ylabel("准确率", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("树越多，OOB 越接近测试；50 棵后基本饱和", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-树数与OOB.png", dpi=130)
    plt.close(fig)


def make_importance() -> None:
    X_tr, _, y_tr, _ = D.make_high_dim()
    hand = impl.RandomForest(n_trees=100, random_state=0).fit(X_tr, y_tr)
    sk = framework.fit_forest(X_tr, y_tr)
    idx = np.arange(X_tr.shape[1])
    fig, ax = plt.subplots(figsize=(9.8, 5.4))
    ax.bar(idx - 0.2, hand.feature_importances_, width=0.4, color=COLOR["forest"],
           label="手写")
    ax.bar(idx + 0.2, sk.feature_importances_, width=0.4, color=COLOR["oob"], alpha=0.8,
           label="sklearn")
    ax.axvspan(-0.5, 3.5, color=COLOR["hl"], alpha=0.18, label="真特征 x0–x3")
    ax.set_xticks(idx)
    ax.set_xticklabels([f"x{i}" for i in idx], fontsize=8.5)
    ax.set_ylabel("归一化重要性", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9.5)
    ax.set_title("真特征的重要性明显高，噪声接近均匀", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-特征重要性.png", dpi=130)
    plt.close(fig)


def make_animation() -> None:
    X_tr, _, y_tr, _ = D.make_moons_data()
    forest = impl.RandomForest(n_trees=100, random_state=0).fit(X_tr, y_tr)
    grid, xx, yy = _grid(X_tr, pad=0.35)
    frames = [1, 2, 5, 10, 25, 50, 100]
    fig, ax = plt.subplots(figsize=(7.6, 6.0))

    def draw(k: int) -> None:
        ax.clear()
        p = _proba(forest, grid, k).reshape(xx.shape)
        ax.contourf(xx, yy, p, levels=[0, 0.5, 1], colors=["#dbe4ff", "#ffe3e3"], alpha=0.85)
        ax.contour(xx, yy, p, levels=[0.5], colors=[COLOR["forest"]], linewidths=2)
        ax.scatter(X_tr[y_tr == 0, 0], X_tr[y_tr == 0, 1], s=11, color=COLOR["neg"], alpha=0.7)
        ax.scatter(X_tr[y_tr == 1, 0], X_tr[y_tr == 1, 1], s=11, color=COLOR["pos"], alpha=0.7)
        ax.set_title(f"前 {k} 棵树的平均边界", fontsize=12)
        ax.set_xlabel("x0")
        ax.set_ylabel("x1")

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=900)
    anim.save(IMAGES / "03-森林投票.gif", writer=animation.PillowWriter(fps=1.2))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画单树/森林边界 …")
    make_boundary()
    print("② 画树数与 OOB …")
    make_n_trees()
    print("③ 画特征重要性 …")
    make_importance()
    print("④ 画森林投票动画 …")
    make_animation()
    print("\n产出：")
    for name in ("00-单树与森林边界.png", "01-树数与OOB.png", "02-特征重要性.png",
                 "03-森林投票.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
