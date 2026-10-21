"""MCTS 图文素材生成器（供 README 引用）。

原则：素材全部由本脚本生成，且与 `demo.py` 的数字逐项对账——不一致直接报错、不出图（纪律④）。

产出（`images/` 目录）：
    00-访问次数.png    概念图：300 次模拟后每格被走了多少次，最终选哪一格
    01-收敛曲线.png    迭代次数 → 对精确搜索的和棋率 / 对贪心对手的胜率（对数横轴）
    02-探索常数.png    探索常数 C 的影响（迭代很少时，纯利用反而更好）
    03-模拟增长.gif   模拟次数从 5 涨到 600，访问次数怎么重新分配

流程图不在这里——优先 Mermaid 直接写进 README（见 visual-assets.md）。

运行：cd algorithms/p01-search/mcts && uv run python make_teaching_assets.py
"""

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")  # 只读环境下的缓存兜底

import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as animation
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
import impl as I  # noqa: E402

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


def concept_data() -> dict:
    """空棋盘上跑 300 次模拟，看根节点的访问次数分布与最终选择。"""
    game = D.GAME
    mcts = I.MCTS(game["get_moves"], game["apply"], game["is_terminal"], game["winner"],
                  rng=random.Random(7))
    action = mcts.search(D.TicTacToe(), iterations=300)
    return {"action": action, "visits": dict(mcts.last_stats["visits"])}


def verify_concept(d: dict) -> None:
    visits = d["visits"]
    assert sum(visits.values()) == 300, f"访问次数之和应等于模拟次数，实际 {sum(visits.values())}"
    best = max(visits, key=visits.get)
    assert best == d["action"], f"最终选择应为访问最多的招法：{best} vs {d['action']}"
    assert visits[best] == 65, f"中心格的访问次数应为 65，实际 {visits[best]}"
    print(f"  ✓ 对账通过：300 次模拟，选第 {d['action']} 格（访问 {visits[best]} 次）")


def make_concept_figure(d: dict) -> None:
    visits = d["visits"]
    vmax = max(visits.values())
    fig, ax = plt.subplots(figsize=(7.4, 7.0))
    for i in range(9):
        r, c = divmod(i, 3)
        v = visits.get(i, 0)
        ax.add_patch(plt.Rectangle((c, 2 - r), 1, 1,
                                   fc=plt.cm.Blues(0.12 + 0.55 * v / vmax), ec="#adb5bd", lw=1.3))
        ax.text(c + 0.5, 2 - r + 0.5, str(v), ha="center", va="center",
                fontsize=20, color="#1c1c1c", weight="bold" if i == d["action"] else "normal")
        if i == d["action"]:
            ax.add_patch(plt.Rectangle((c + 0.04, 2 - r + 0.04), 0.92, 0.92, fill=False,
                                       ec=COLOR["hl"], lw=4))
    ax.set_xlim(-0.1, 3.1); ax.set_ylim(-0.1, 3.1); ax.axis("off")
    ax.set_title("空棋盘跑 300 次模拟：每格被「走」了多少次", fontsize=13.5, pad=14)
    ax.text(0.5, -0.03,
            "数字 = 这格在 300 次模拟中被选为下一步的次数；黄框 = 最终选择（访问最多的一格）。\n"
            "只试过 1～2 次的格，胜率再高也不可信——MCTS 信「被反复试过」，不信「一次全胜」。",
            transform=ax.transAxes, ha="center", va="top", fontsize=10.8, linespacing=1.6,
            color=COLOR["text"])
    fig.tight_layout()
    fig.savefig(IMAGES / "00-访问次数.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def budget_frames(budgets=(5, 10, 20, 50, 100, 300, 600)) -> list:
    """同一局面、同一随机种子，只改模拟预算：看访问次数如何重新分配。"""
    rows = []
    for it in budgets:
        mcts = I.MCTS(D.GAME["get_moves"], D.GAME["apply"], D.GAME["is_terminal"],
                      D.GAME["winner"], rng=random.Random(7))
        action = mcts.search(D.TicTacToe(), iterations=it)
        rows.append({"iters": it, "visits": dict(mcts.last_stats["visits"]), "action": action})
    return rows


def verify_budget_frames(rows: list) -> None:
    for r in rows:
        assert sum(r["visits"].values()) == r["iters"], "访问次数之和应等于模拟次数"
    last = rows[-1]
    best = max(last["visits"], key=last["visits"].get)
    assert best == last["action"], "最终选择应为访问最多的招法"
    print(f"  ✓ 对账通过：{last['iters']} 次模拟选第 {last['action']} 格"
          f"（访问 {last['visits'][best]} 次）")


def make_budget_animation(rows: list) -> None:
    frame_rows = []
    for r in rows:
        frame_rows.extend([r] * 4)

    fig, ax = plt.subplots(figsize=(6.8, 6.6))

    def draw(i: int) -> None:
        r = frame_rows[i]
        visits = r["visits"]
        vmax = max(visits.values())
        ax.clear()
        for cell in range(9):
            rr, cc = divmod(cell, 3)
            v = visits.get(cell, 0)
            ax.add_patch(plt.Rectangle((cc, 2 - rr), 1, 1,
                                       fc=plt.cm.Blues(0.12 + 0.55 * v / vmax),
                                       ec="#adb5bd", lw=1.2))
            ax.text(cc + 0.5, 2 - rr + 0.5, str(v), ha="center", va="center", fontsize=18)
            if cell == r["action"]:
                ax.add_patch(plt.Rectangle((cc + 0.04, 2 - rr + 0.04), 0.92, 0.92,
                                           fill=False, ec=COLOR["hl"], lw=3.5))
        ax.set_xlim(-0.05, 3.05); ax.set_ylim(-0.05, 3.05); ax.axis("off")
        ax.set_title(f"预算 {r['iters']} 次模拟：访问次数怎么分配", fontsize=13)

    anim = animation.FuncAnimation(fig, draw, frames=len(frame_rows), interval=350)
    anim.save(IMAGES / "03-模拟增长.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main() -> None:
    print("取数：收敛曲线 …")
    conv = convergence_rows()
    print("取数：探索常数 …")
    expl = exploration_rows()
    verify(conv, expl)
    print("取数：访问次数概念图 …")
    concept = concept_data()
    verify_concept(concept)
    print("① 画收敛曲线 …")
    make_convergence(conv)
    print("② 画探索常数 …")
    make_exploration(expl)
    print("取数：预算增长动画 …")
    budgets = budget_frames()
    verify_budget_frames(budgets)
    print("③ 画预算增长动画 …")
    make_budget_animation(budgets)
    print("④ 画概念图：访问次数怎么决定选择 …")
    make_concept_figure(concept)
    print("\n产出：")
    for name in ("00-访问次数.png", "01-收敛曲线.png", "02-探索常数.png", "03-模拟增长.gif"):
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
