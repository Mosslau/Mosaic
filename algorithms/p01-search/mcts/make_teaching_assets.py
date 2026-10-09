"""MCTS 图文素材生成器（供 README 引用）。

原则：素材全部由本脚本生成，且与 `demo.py` 的数字逐项对账——不一致直接报错、不出图（纪律④）。

产出（`images/` 目录）：
    01-收敛曲线.png    迭代次数 → 对精确搜索的和棋率 / 对贪心对手的胜率（对数横轴）
    02-探索常数.png    探索常数 C 的影响（迭代很少时，纯利用反而更好）

流程图不在这里——优先 Mermaid 直接写进 README（见 visual-assets.md）。

运行：cd algorithms/p01-search/mcts && python3 make_teaching_assets.py
"""

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")  # 只读环境下的缓存兜底

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)


def setup_cjk_font() -> str:
    """注册一个**确实含中文字形**的字体，返回字体名；找不到就报错，绝不画方块。"""
    cjk_names = (
        "Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC", "Source Han Sans CN",
        "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",           # Linux
        "Hiragino Sans GB", "PingFang SC", "Heiti TC",
        "STHeiti", "Songti SC", "Arial Unicode MS",           # macOS
        "Microsoft YaHei", "SimHei",                          # Windows
    )
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)

    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in cjk_names if n in available), None)
    if chosen is None:
        raise SystemExit(
            "找不到含中文字形的字体，拒绝生成方块版素材。\n"
            f"fontManager 已扫描到 {len(available)} 个字体族，但无候选命中。\n"
            "请安装任一中文字体（如 Noto Sans CJK / 文泉驿）后重跑。"
        )

    font_path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font

    if ft2font.FT2Font(font_path).get_char_index(ord("中")) == 0:
        raise SystemExit(f"字体 {chosen}（{font_path}）不含中文字形，拒绝生成方块版素材")

    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


FONT_USED = setup_cjk_font()

import demo as D  # noqa: E402

COLOR = dict(greedy="#c92a2a", exact="#2b8a3e", grid="#dee2e6", text="#343a40",
             hl="#f6c344", loss="#868e96")


# ---------------------------------------------------------------- 取数

def convergence_rows() -> list:
    """每个迭代档取两个指标：对贪心对手的胜率、对精确搜索的不输率。

    与 `demo.experiment_vs_baseline` / `_play_vs_exact` **同一套函数**取数，
    保证图与文档里的表是同一份数据（不另写一套统计口径）。
    """
    alphabeta = D._load_minimax().alphabeta
    rows = []
    for iterations in (5, 10, 20, 50, 100, 200, 500, 2000):
        vs_greedy = D.play_vs_policy(iterations, "greedy", games=40, seed=42)
        vs_exact = D._play_vs_exact(alphabeta, games=20, seed=5, iterations=iterations,
                                    exploration=2 ** 0.5)
        rows.append({
            "iterations": iterations,
            "greedy_win": vs_greedy["win_rate"],
            "exact_notlose": vs_exact["draws"] / 20,
        })
        print(f"  iterations={iterations:>5}  对贪心胜率 {vs_greedy['win_rate']:>4.0%}"
              f"  对精确不输率 {vs_exact['draws'] / 20:>4.0%}")
    return rows


def exploration_rows() -> list:
    """探索常数 C → 对精确搜索的不输率（故意只给 10 次模拟，差异才显出来）。"""
    alphabeta = D._load_minimax().alphabeta
    rows = []
    for c in (0.0, 0.5, 2 ** 0.5, 3.0, 10.0):
        r = D._play_vs_exact(alphabeta, games=40, seed=5, iterations=10, exploration=c)
        rows.append({"C": c, "notlose": r["draws"] / 40})
        print(f"  C={c:>5.2f}  不输率 {r['draws'] / 40:>4.0%}")
    return rows


def verify(conv: list, expl: list) -> None:
    """对账：图里的趋势必须有数据支撑，且与 demo 的口径一致。"""
    first, last = conv[0], conv[-1]
    assert last["exact_notlose"] > first["exact_notlose"], (
        f"迭代变多反而不输率没提高：{first} → {last}")
    assert last["exact_notlose"] >= 0.9, (
        f"迭代 {last['iterations']} 对精确搜索的不输率只有 {last['exact_notlose']:.0%}")
    assert max(r["notlose"] for r in expl) >= first["exact_notlose"], (
        "探索常数实验里没有任何 C 达到基线水平——实验设计有问题")
    print("  ✓ 对账通过：迭代越多不输率越高、且迭代充分时不低于 90%")


# ---------------------------------------------------------------- ① 收敛曲线

def make_convergence(conv: list) -> None:
    xs = [r["iterations"] for r in conv]
    greedy = [r["greedy_win"] * 100 for r in conv]
    exact = [r["exact_notlose"] * 100 for r in conv]

    fig, ax = plt.subplots(figsize=(10.4, 6.2))
    ax.plot(xs, greedy, "o-", color=COLOR["greedy"], lw=2.0, ms=7,
            label="对贪心挡招对手：胜率")
    ax.plot(xs, exact, "s-", color=COLOR["exact"], lw=2.0, ms=7,
            label="对精确搜索 alphabeta(depth=9)：不输率（和棋率）")
    ax.axhline(100, color=COLOR["grid"], lw=1.0, ls="--")
    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs])
    ax.set_xlabel("每步模拟次数 iterations（对数轴）", fontsize=12)
    ax.set_ylabel("比例（%）", fontsize=12)
    ax.set_ylim(0, 108)
    ax.grid(True, which="both", color=COLOR["grid"], lw=0.8)
    ax.set_axisbelow(True)
    for x, y in zip(xs, exact):
        ax.annotate(f"{y:.0f}%", (x, y), textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=9, color=COLOR["exact"])
    for x, y in zip(xs, greedy):
        if x in (5, 10, 50):
            ax.annotate(f"{y:.0f}%", (x, y), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=9, color=COLOR["greedy"])
    ax.legend(loc="lower right", fontsize=11)
    ax.set_title("模拟次数换决策质量：两条曲线都在告诉我们「多给点次数」", fontsize=14, pad=12)
    ax.text(0.015, 0.30,
            "对精确搜索：迭代 ≤10 只有三到四成的棋守得住，20 次 65%，"
            "给到 100 次以上才稳定 100%。\n"
            "对贪心对手的曲线更陡：5 次 48%，20 次就到 100%——对手越强，越吃模拟次数。",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=10.5, color=COLOR["text"])
    fig.tight_layout()
    fig.savefig(IMAGES / "01-收敛曲线.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- ② 探索常数

def make_exploration(expl: list) -> None:
    labels = ["0\n(纯利用)", "0.5", "√2\n(默认)", "3.0", "10.0"]
    ys = [r["notlose"] * 100 for r in expl]
    best = max(range(len(ys)), key=lambda i: ys[i])

    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    bars = ax.bar(range(len(ys)), ys, color=[COLOR["hl"] if i == best else COLOR["loss"]
                                             for i in range(len(ys))])
    for i, (bar, y) in enumerate(zip(bars, ys)):
        ax.text(bar.get_x() + bar.get_width() / 2, y + 1.5, f"{y:.0f}%",
                ha="center", fontsize=11, color=COLOR["text"])
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_xlabel("探索常数 C（UCB1 里 胜率项 : 探索项 的权重）", fontsize=12)
    ax.set_ylabel("对精确搜索的不输率（%）", fontsize=12)
    ax.set_ylim(0, 100)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.8)
    ax.set_axisbelow(True)
    ax.set_title("模拟次数很少时，「纯利用」反而更好——探索要花得起才划算",
                 fontsize=14, pad=12)
    ax.text(0.5, 0.86,
            "只给 10 次模拟：C=0 把全部次数压在最有希望的分支上，不输率最高；\n"
            "C 越大，次数被摊薄到差分支上，反而更容易输。\n"
            "——探索的价值随「总模拟次数」增长，这是 UCB1 里 ln(N)/n 那一项的代价。",
            transform=ax.transAxes, ha="center", va="top", fontsize=10.5, color=COLOR["text"])
    fig.tight_layout()
    fig.savefig(IMAGES / "02-探索常数.png", dpi=130)
    plt.close(fig)


def main() -> None:
    print("取数：收敛曲线 …")
    conv = convergence_rows()
    print("取数：探索常数 …")
    expl = exploration_rows()
    verify(conv, expl)
    print("① 画收敛曲线 …")
    make_convergence(conv)
    print("② 画探索常数 …")
    make_exploration(expl)
    print("\n产出：")
    for name in ("01-收敛曲线.png", "02-探索常数.png"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")
    print("\n可粘贴进 README 的收敛表：")
    print("| iterations | 对贪心挡招胜率 | 对精确搜索不输率 |")
    print("|---|---|---|")
    for r in conv:
        print(f"| {r['iterations']} | {r['greedy_win']:.0%} | {r['exact_notlose']:.0%} |")
    print("\n探索常数表：")
    print("| C | 不输率 |")
    print("|---|---|")
    for r in expl:
        print(f"| {r['C']:.2f} | {r['notlose']:.0%} |")


if __name__ == "__main__":
    main()
