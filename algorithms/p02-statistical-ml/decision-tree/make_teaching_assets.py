"""决策树 ID3/CART — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-决策边界与树结构.png  深度 3 的划分区域 + 对应的树结构
    01-深度与过拟合.png      训练/测试准确率、叶子数随深度的变化
    02-剪枝曲线.png          ccp_alpha 与测试准确率/叶子数
    03-树的生长.gif          深度 1→8 的决策边界演化

运行：cd algorithms/p02-statistical-ml/decision-tree && uv run python make_teaching_assets.py
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
             hl="#f6c344", text="#343a40", leaf="#e9ecef", node="#dbe4ff")


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.make_data()
    hand = impl.DecisionTree(max_depth=4).fit(X_tr, y_tr)
    sk = framework.fit_tree(X_tr, y_tr, max_depth=4)
    assert hand.get_n_leaves() == sk.get_n_leaves(), "手写与 sklearn 叶子数不一致"
    assert np.mean(hand.predict(X_te) == sk.predict(X_te)) > 0.98, "手写与 sklearn 预测不一致"
    full = impl.DecisionTree().fit(X_tr, y_tr)
    pruned = impl.DecisionTree(ccp_alpha=0.02).fit(X_tr, y_tr)
    assert pruned.get_n_leaves() < full.get_n_leaves(), "剪枝未减少叶子"
    print(f"  ✓ 对账通过：depth=4 叶子 {hand.get_n_leaves()}（sklearn 同）、"
          f"预测一致率 {np.mean(hand.predict(X_te) == sk.predict(X_te)):.3f}；"
          f"剪枝 {full.get_n_leaves()}→{pruned.get_n_leaves()} 叶")


def regions(ax, model, X, y) -> None:
    xx, yy = np.meshgrid(np.linspace(X[:, 0].min() - 0.3, X[:, 0].max() + 0.3, 250),
                         np.linspace(X[:, 1].min() - 0.3, X[:, 1].max() + 0.3, 250))
    z = model.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
    ax.contourf(xx, yy, z, levels=[-0.5, 0.5, 1.5], colors=["#dbe4ff", "#ffe3e3"], alpha=0.8)
    ax.scatter(X[y == 0, 0], X[y == 0, 1], s=12, color=COLOR["neg"], alpha=0.8, label="类别 0")
    ax.scatter(X[y == 1, 0], X[y == 1, 1], s=12, color=COLOR["pos"], alpha=0.8, label="类别 1")


def make_tree_diagram(ax, node, x=0.0, y=0.0, width=1.0) -> None:
    """递归画树：叶子按顺序占横坐标，内部节点取子节点中点。"""
    if "feature" not in node:
        ax.text(x, y, f"叶 {node['value']}\nn={node['n']}", ha="center", va="center",
                fontsize=7.5, bbox=dict(boxstyle="round,pad=0.25", fc=COLOR["leaf"],
                                        ec=COLOR["text"], lw=0.6))
        return
    ax.text(x, y, f"x{node['feature']} ≤ {node['threshold']:.2f}", ha="center", va="center",
            fontsize=7.5, bbox=dict(boxstyle="round,pad=0.25", fc=COLOR["node"],
                                    ec=COLOR["text"], lw=0.6))
    # 先算左右子树位置：按叶子数分配横坐标
    def count_leaves(n):
        return 1 if "feature" not in n else count_leaves(n["left"]) + count_leaves(n["right"])

    n_left = count_leaves(node["left"])
    n_all = n_left + count_leaves(node["right"])
    xl = x - width * (n_all - n_left) / (2 * n_all) if n_all else x
    xr = x + width * n_left / (2 * n_all) if n_all else x
    y2 = y - 0.28
    ax.plot([x, xl], [y - 0.05, y2 + 0.05], color=COLOR["text"], lw=0.7)
    ax.plot([x, xr], [y - 0.05, y2 + 0.05], color=COLOR["text"], lw=0.7)
    make_tree_diagram(ax, node["left"], xl, y2, width * n_left / n_all)
    make_tree_diagram(ax, node["right"], xr, y2, width - width * n_left / n_all)


def make_boundary_and_tree() -> None:
    X_tr, _, y_tr, _ = D.make_data()
    model = impl.DecisionTree(max_depth=3).fit(X_tr, y_tr)
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 6.0))
    regions(axes[0], model, X_tr, y_tr)
    axes[0].set_title(f"深度 3 的决策区域（{model.get_n_leaves()} 个叶子）", fontsize=12.5)
    axes[0].set_xlabel("x0")
    axes[0].set_ylabel("x1")
    axes[0].legend(fontsize=9, loc="upper right")

    axes[1].axis("off")
    make_tree_diagram(axes[1], model.root, x=0.5, y=0.95, width=0.9)
    axes[1].set_xlim(0, 1)
    axes[1].set_ylim(-0.05, 1.02)
    axes[1].set_title("同一棵树的递归结构", fontsize=12.5)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-决策边界与树结构.png", dpi=130)
    plt.close(fig)


def make_depth_curve() -> None:
    X_tr, X_te, y_tr, y_te = D.make_data()
    depths = list(range(1, 11))
    train, test, leaves = [], [], []
    for d in depths:
        m = impl.DecisionTree(max_depth=d).fit(X_tr, y_tr)
        train.append(D.accuracy(y_tr, m.predict(X_tr)))
        test.append(D.accuracy(y_te, m.predict(X_te)))
        leaves.append(m.get_n_leaves())
    fig, ax1 = plt.subplots(figsize=(9.6, 5.6))
    ax1.plot(depths, train, "o-", color=COLOR["line"], lw=2, label="训练准确率")
    ax1.plot(depths, test, "s-", color=COLOR["pos"], lw=2, label="测试准确率")
    ax1.set_xlabel("max_depth", fontsize=12)
    ax1.set_ylabel("准确率", fontsize=12)
    ax1.set_ylim(0.5, 1.02)
    ax1.grid(True, color=COLOR["grid"], lw=0.7)
    ax1.set_axisbelow(True)
    ax2 = ax1.twinx()
    ax2.bar(depths, leaves, alpha=0.25, color=COLOR["hl"], label="叶子数")
    ax2.set_ylabel("叶子数", fontsize=12)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9.5, loc="lower right")
    ax1.set_title("越深越会背训练集：训练升、测试先升后平/降", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-深度与过拟合.png", dpi=130)
    plt.close(fig)


def make_pruning_curve() -> None:
    X_tr, X_te, y_tr, y_te = D.make_data()
    alphas, _ = framework.pruning_path(X_tr, y_tr)
    alphas = np.unique(np.quantile(alphas, np.linspace(0, 1, 25)))
    test, leaves = [], []
    for a in alphas:
        m = impl.DecisionTree(ccp_alpha=float(a)).fit(X_tr, y_tr)
        test.append(D.accuracy(y_te, m.predict(X_te)))
        leaves.append(m.get_n_leaves())
    fig, ax1 = plt.subplots(figsize=(9.6, 5.6))
    ax1.plot(alphas, test, "o-", color=COLOR["line"], lw=2, label="测试准确率")
    ax1.set_xlabel("ccp_alpha", fontsize=12)
    ax1.set_ylabel("测试准确率", fontsize=12, color=COLOR["line"])
    ax1.grid(True, color=COLOR["grid"], lw=0.7)
    ax1.set_axisbelow(True)
    ax2 = ax1.twinx()
    ax2.plot(alphas, leaves, "s--", color=COLOR["pos"], lw=1.5, label="叶子数")
    ax2.set_ylabel("叶子数", fontsize=12, color=COLOR["pos"])
    best = alphas[int(np.argmax(test))]
    ax1.axvline(best, color=COLOR["hl"], lw=2, ls=":", label=f"最优 alpha≈{best:.3f}")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9.5)
    ax1.set_title("剪枝：alpha 太小树仍复杂，太大欠拟合", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-剪枝曲线.png", dpi=130)
    plt.close(fig)


def make_animation() -> None:
    X_tr, _, y_tr, _ = D.make_data()
    fig, ax = plt.subplots(figsize=(7.4, 6.2))
    frames = list(range(1, 9))

    def draw(depth: int) -> None:
        ax.clear()
        model = impl.DecisionTree(max_depth=depth).fit(X_tr, y_tr)
        regions(ax, model, X_tr, y_tr)
        ax.set_title(f"max_depth = {depth}（{model.get_n_leaves()} 个叶子）", fontsize=12)
        ax.set_xlabel("x0")
        ax.set_ylabel("x1")

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=700)
    anim.save(IMAGES / "03-树的生长.gif", writer=animation.PillowWriter(fps=1.4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画决策边界与树结构 …")
    make_boundary_and_tree()
    print("② 画深度曲线 …")
    make_depth_curve()
    print("③ 画剪枝曲线 …")
    make_pruning_curve()
    print("④ 画树的生长 …")
    make_animation()
    print("\n产出：")
    for name in ("00-决策边界与树结构.png", "01-深度与过拟合.png", "02-剪枝曲线.png",
                 "03-树的生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
