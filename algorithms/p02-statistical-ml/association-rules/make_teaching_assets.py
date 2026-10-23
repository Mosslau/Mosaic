"""关联规则 — 素材生成器。"""

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

from demo import make_transactions  # noqa: E402
from impl import Apriori, brute_force  # noqa: E402


def setup():
    trans = make_transactions(300, seed=0)
    ap = Apriori(min_support=0.05, max_len=3).fit(trans)
    return trans, ap, ap.rules(0.5)


def verify() -> None:
    trans, ap, rules = setup()
    small = trans[:60]
    bf = brute_force(small, 0.05, 3)
    a2 = Apriori(0.05, 3).fit(small)
    assert set(a2.frequent_itemsets_) == set(bf) and rules
    print(f"  ✓ 对账通过：频繁项集 {len(a2.frequent_itemsets_)} == 暴力 {len(bf)}")


def make_scatter() -> None:
    _, _, rules = setup()
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    sc = ax.scatter([r.support for r in rules], [r.confidence for r in rules],
                    c=[r.lift for r in rules], cmap="viridis", s=14)
    ax.set_xlabel("support")
    ax.set_ylabel("confidence")
    ax.set_title("规则分布：support × confidence（颜色=lift）", fontsize=12)
    fig.colorbar(sc, ax=ax, label="lift")
    fig.tight_layout()
    fig.savefig(IMAGES / "00-规则散点.png", dpi=130)
    plt.close(fig)


def make_top() -> None:
    _, _, rules = setup()
    top = rules[:8][::-1]
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    labels = [f"{','.join(sorted(r.antecedent))}→{','.join(sorted(r.consequent))}"
              for r in top]
    ax.barh(labels, [r.lift for r in top], color="#3b5bdb")
    ax.set_xlabel("lift")
    ax.set_title("Top 8 规则（按 lift/confidence）", fontsize=12)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-Top规则.png", dpi=130)
    plt.close(fig)


def make_network() -> None:
    _, ap, _ = setup()
    # 边 = 2-项集的 support；节点按圆环排
    items = sorted({x for s in ap.frequent_itemsets_ for x in s})
    pos = {it: (np.cos(2 * np.pi * i / len(items)), np.sin(2 * np.pi * i / len(items)))
           for i, it in enumerate(items)}
    fig, ax = plt.subplots(figsize=(6.6, 6.0))
    for s, sup in ap.frequent_itemsets_.items():
        if len(s) != 2:
            continue
        a, b = sorted(s)
        ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]],
                color="#3b5bdb", alpha=min(1.0, sup * 2), lw=1 + 4 * sup)
    for it, (x, y) in pos.items():
        ax.scatter([x], [y], s=120, color="#f08c00")
        ax.text(x * 1.12, y * 1.12, it, ha="center", fontsize=9)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("2-项集共现网络（线宽/透明度=support）", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-规则网络.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    trans = make_transactions(300, seed=0)
    thresholds = np.linspace(0.03, 0.15, 9)
    counts = []
    for th in thresholds:
        ap = Apriori(th, 3).fit(trans)
        counts.append(len(ap.rules(0.5)))
    fig, ax = plt.subplots(figsize=(6.4, 4.2))

    def draw(i):
        ax.clear()
        ax.plot(thresholds[:i + 1], counts[:i + 1], "o-", color="#3b5bdb")
        ax.set_xlim(0.03, 0.15)
        ax.set_ylim(0, max(counts) * 1.1)
        ax.set_xlabel("min_support")
        ax.set_ylabel("规则数")
        ax.set_title(f"min_support={thresholds[i]:.3f}，规则 {counts[i]}")

    anim = animation.FuncAnimation(fig, draw, frames=len(thresholds), interval=500)
    anim.save(IMAGES / "03-支持度扫描.gif", writer=animation.PillowWriter(fps=2))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 散点 …")
    make_scatter()
    print("② Top …")
    make_top()
    print("③ 网络 …")
    make_network()
    print("④ GIF …")
    make_gif()
    print("\n产出：")
    for name in ("00-规则散点.png", "01-Top规则.png", "02-规则网络.png", "03-支持度扫描.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
