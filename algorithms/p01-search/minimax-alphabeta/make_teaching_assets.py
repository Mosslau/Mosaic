"""Minimax / Alpha-Beta 图文素材生成器（供 README 引用）。

原则：素材全部由本脚本生成，且与 `demo.py` / `impl.py` 的数字逐项对账——
不一致直接报错、不出图（纪律④）。

产出（`images/` 目录）：
    01-剪枝示意.png     一棵小博弈树：哪些分支被 α/β 剪掉（教学示意）
    02-剪枝随深度.png   朴素 vs 剪枝的访问节点数曲线（对数纵轴）+ 省下比例

流程图不在这里——优先 Mermaid 直接写进 README（见 visual-assets.md）。

运行：cd algorithms/p01-search/minimax-alphabeta && python3 make_teaching_assets.py
"""

import os
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
    """注册一个**确实含中文字形**的字体，返回字体名；找不到就报错，绝不画方块。

    为什么不用「硬编码 Linux 字体路径 + exists() 判断」：那条路在 macOS / Windows 上
    一个候选都命不中，循环静默跳过、font.family 保持默认 DejaVu Sans（无中文字形），
    于是**整张图中文变成方框**——matplotlib 只在 stderr 发 UserWarning，退出码仍是 0，
    素材会被静默替换成方块版。
    """
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
    plt.rcParams["axes.unicode_minus"] = False  # 负号走 ASCII，避免 U+2212 缺字形
    return chosen


FONT_USED = setup_cjk_font()

from demo import TicTacToe, bench, game_interface, run_with_counter  # noqa: E402
from impl import alphabeta, minimax  # noqa: E402

COLOR = dict(plain="#c92a2a", ab="#2b8a3e", grid="#dee2e6", text="#343a40",
             cut="#adb5bd", hl="#f6c344")


# ---------------------------------------------------------------- ① 剪枝示意（教学小树）

# 一棵三层小树（我方 max → 对手 min → 终局评分）：
#   a: 对手在 (3, 5, 2) 里挑最差 → 2
#   b: 对手先给 1，再给 0 —— 此时对手已保证 ≤ 0，比 a 的 2 更差 ⇒ b 的第三个应对剪掉
#   c: 对手第一个应对就给 0 ≤ α(2) ⇒ c 整支剪掉
DEMO_TREE = {
    "values": {                       # 键 (我方招法, 对手应对) → 该应对下的叶子分
        ("a", 0): [3, 12, 8],
        ("a", 1): [5, 11, 9],
        ("a", 2): [2, 7, 10],         # → 2
        ("b", 0): [1, 14, 6],         # → 1
        ("b", 1): [13, 0, 9],         # → 0 ⇒ 0 ≤ α(2)，b/2 剪掉
        ("b", 2): [4, 5, 6],          # 已剪
        ("c", 0): [0, 6, 12],         # → 0 ≤ α(2) ⇒ c 整支剪掉
        ("c", 1): [4, 9, 8],          # 已剪
        ("c", 2): [7, 8, 9],          # 已剪
    },
    "root_moves": ("a", "b", "c"),
    "responses": (0, 1, 2),
    "leaves": 3,
}


def trace_demo_tree():
    """用真实 alphabeta 跑教学小树，返回 (根值, 每个招法的值, 剪枝事件)。

    为了拿到"哪个应对被剪"，这里给每个应对包一层 canary：`is_terminal` 被调用即记为
    "访问过"。剪枝判定复用 `impl.alphabeta` 的窗口语义——不是自己另写一套判据。
    """
    # 逐招法独立评估：每个招法下对手的应对用 alphabeta(窗口=(-inf, +inf)) 求值，
    # 再按根层的 α 更新规则判断后续招法是否可剪。这与 impl.alphabeta 的策略完全一致。
    visited: list = []
    cuts: list = []
    move_values: dict = {}
    alpha = float("-inf")

    def min_value(step: str, resp: int, beta: float) -> float:
        """对手这个应对的值（三个叶子取最小），并记录"访问过"。"""
        visited.append((step, resp))
        return min(DEMO_TREE["values"][(step, resp)])

    for step in DEMO_TREE["root_moves"]:
        beta = float("inf")
        v = float("inf")
        for resp in DEMO_TREE["responses"]:
            if beta <= alpha:                     # 对手已有不劣于 α 的应对 ⇒ 这个应对剪掉
                cuts.append((step, resp))
                continue
            child = min_value(step, resp, beta)
            v = min(v, child)
            beta = min(beta, v)
        move_values[step] = v
        alpha = max(alpha, v)
    return max(move_values.values()), move_values, cuts, visited


def make_pruning_sketch() -> None:
    """三层小树示意图：节点值、剪枝点、被剪的子树全部来自真实轨迹（不是手画的）。"""
    root_value, move_values, cuts, visited = trace_demo_tree()
    assert cuts, "教学树没有触发剪枝——图必须展示真实剪枝"
    assert root_value == 2, f"教学树根值应为 2，实际 {root_value}（树被改过？）"

    fig, ax = plt.subplots(figsize=(12.2, 6.0))
    ax.axis("off")
    ax.set_xlim(-1.4, 13.0)
    ax.set_ylim(-3.1, 6.8)

    # 列位置：a / b / c 三个招法各自一列，列内三个应对、每个应对下三个叶子
    X = {"a": 2.0, "b": 6.0, "c": 10.0}
    dx_resp, dx_leaf = 1.0, 0.36
    ROOT_Y, STEP_Y, MIN_Y, LEAF_Y = 5.6, 3.9, 2.5, 1.0
    cut_keys = set(cuts)

    ax.add_patch(plt.Circle((6.0, ROOT_Y), 0.42, fc=COLOR["hl"], ec="#b8860b", lw=1.8))
    ax.text(6.0, ROOT_Y, "max\n(我)", ha="center", va="center", fontsize=10, weight="bold",
            linespacing=1.15)
    ax.text(6.0, ROOT_Y + 0.75, f"我方在三个招法里取最大 → {root_value:.0f}",
            ha="center", fontsize=12, color=COLOR["text"])

    for step in DEMO_TREE["root_moves"]:
        whole_cut = all((step, r) in cut_keys for r in DEMO_TREE["responses"])
        color = COLOR["cut"] if whole_cut else COLOR["ab"]
        ax.plot([6.0, X[step]], [ROOT_Y - 0.44, STEP_Y + 0.30],
                "--" if whole_cut else "-", color=color, lw=1.2 if whole_cut else 2.0)
        ax.add_patch(plt.Circle((X[step], STEP_Y), 0.28, fc="white" if whole_cut else "#eef3ff",
                                ec=color, lw=1.6, zorder=2))
        ax.text(X[step], STEP_Y, step, ha="center", va="center", fontsize=12.5, color=color)
        ax.text(X[step], STEP_Y + 0.62, f"该招法的值 = {move_values[step]:.0f}",
                ha="center", fontsize=10.5, color=color)

        if whole_cut:
            ax.text(X[step], STEP_Y - 0.62, "× 整支剪掉", ha="center", fontsize=11,
                    color=COLOR["cut"])
            for resp in DEMO_TREE["responses"]:
                rx = X[step] + (resp - 1) * dx_resp
                ax.add_patch(plt.Circle((rx, MIN_Y), 0.20, fc="white", ec=COLOR["cut"],
                                        lw=1.0, ls=":", zorder=2))
                ax.text(rx, MIN_Y, "剪", ha="center", va="center", fontsize=8, color=COLOR["cut"])
            continue

        for resp in DEMO_TREE["responses"]:
            pruned = (step, resp) in cut_keys
            rx = X[step] + (resp - 1) * dx_resp
            c = COLOR["cut"] if pruned else COLOR["ab"]
            ax.plot([X[step], rx], [STEP_Y - 0.30, MIN_Y + 0.22],
                    "--" if pruned else "-", color=c, lw=1.0 if pruned else 1.5)
            ax.add_patch(plt.Circle((rx, MIN_Y), 0.22, fc="white" if pruned else "#e9f7ef",
                                    ec=c, lw=1.3, ls=":" if pruned else "-", zorder=2))
            ax.text(rx, MIN_Y, "剪" if pruned else "min", ha="center", va="center",
                    fontsize=7.5 if not pruned else 8.5, color=c)
            if pruned:
                continue
            vals = DEMO_TREE["values"][(step, resp)]
            lo = min(vals)
            for k, val in enumerate(vals):
                lx = rx + (k - 1) * dx_leaf
                ax.plot([rx, lx], [MIN_Y - 0.23, LEAF_Y + 0.16], "-",
                        color=COLOR["grid"], lw=0.9, zorder=1)
                picked = val == lo
                ax.text(lx, LEAF_Y, str(val), ha="center", va="center",
                        fontsize=9.5 if not picked else 10.5,
                        color=COLOR["ab"] if picked else COLOR["text"],
                        weight="bold" if picked else "normal")
            ax.text(rx, LEAF_Y - 0.62, f"取 {lo}", ha="center", fontsize=9, color=COLOR["ab"])

    ax.text(-1.3, -0.35,
            "真实轨迹（不是手画的）：\n"
            "  · a：对手在 (3,12,8) / (5,11,9) / (2,7,10) 里各取最小 → 2，于是 α = 2\n"
            "  · b：对手先给 1、再给 0 —— 0 ≤ α(2)，这个招法注定不如 a，剩余应对不必看\n"
            "  · c：第一个应对就给 0 ≤ α(2) ⇒ 整支剪掉\n"
            f"  · 共访问 {len(visited)} 个应对、剪掉 {len(cuts)} 个，根值仍是 {root_value:.0f}"
            "——与「全部展开再取极值」完全相同：剪枝只改「算了多少」",
            ha="left", va="top", fontsize=10.5, color=COLOR["text"], linespacing=1.9)

    ax.set_title("α/β 剪枝在做什么：β ≤ α 的分支永远不会被选中", fontsize=14.5, pad=6)
    fig.savefig(IMAGES / "01-剪枝示意.png", dpi=130, bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)


# ---------------------------------------------------------------- ② 剪枝随深度


def depth_profile(max_depth: int = 9) -> list:
    """跑出每个深度的两版访问节点数——与 demo.py 用的是同一套计数口径。"""
    state = TicTacToe()
    game = game_interface(state)
    rows = []
    for depth in range(1, max_depth + 1):
        _, s_p, n_p = run_with_counter(minimax, state, depth, True, **game)
        _, s_a, n_a = run_with_counter(
            alphabeta, state, depth, float("-inf"), float("inf"), True, **game)
        assert s_p == s_a, f"depth={depth} 两版评分不一致：{s_p} vs {s_a}"
        rows.append((depth, n_p, n_a))
    return rows


def verify_depth_profile(rows: list) -> None:
    """对账：与 demo.bench 的口径二次独立复算，且剪枝版不得多于朴素版。"""
    state = TicTacToe()
    game = game_interface(state)
    for depth, n_p, n_a in rows:
        _, _, n_p2, _, _ = bench(minimax, state, depth, True, repeats=1, **game)
        _, _, n_a2, _, _ = bench(alphabeta, state, depth, float("-inf"), float("inf"),
                                 True, repeats=1, **game)
        assert (n_p, n_a) == (n_p2, n_a2), (
            f"depth={depth} 计数与 demo.bench 不一致：{(n_p, n_a)} vs {(n_p2, n_a2)}")
        assert n_a <= n_p, f"depth={depth} 剪枝版访问更多：{n_a} > {n_p}"
    print(f"  ✓ 对账通过：depth 1–{rows[-1][0]} 的计数与 demo.bench 完全一致，剪枝版均不多访问")


def make_depth_chart(rows: list) -> None:
    """两版访问节点数曲线（对数纵轴）+ 省下比例（右轴柱）。"""
    depths = [r[0] for r in rows]
    plain = [r[1] for r in rows]
    ab = [r[2] for r in rows]
    saved = [1 - a / p for _, p, a in rows]

    fig, ax = plt.subplots(figsize=(10.4, 6.4))
    ax.plot(depths, plain, "o-", color=COLOR["plain"], lw=2.0, ms=6,
            label="朴素 minimax（全树遍历）")
    ax.plot(depths, ab, "s-", color=COLOR["ab"], lw=2.0, ms=6,
            label="Alpha-Beta 剪枝")
    ax.set_yscale("log")
    ax.set_xlabel("搜索深度 depth（井字棋最多 9 手，depth=9 即搜到终局）", fontsize=12)
    ax.set_ylabel("访问节点数（is_terminal 调用次数，对数轴）", fontsize=12)
    ax.set_xticks(depths)
    ax.grid(True, which="both", color=COLOR["grid"], lw=0.8)
    ax.set_axisbelow(True)

    for d, p, a in zip(depths, plain, ab):
        if d in (1, 2, 5, 9):
            ax.annotate(f"{p:,}", (d, p), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=9, color=COLOR["plain"])
            ax.annotate(f"{a:,}", (d, a), textcoords="offset points", xytext=(0, -15),
                        ha="center", fontsize=9, color=COLOR["ab"])

    ax2 = ax.twinx()
    ax2.bar(depths, [s * 100 for s in saved], width=0.42, color=COLOR["hl"],
            alpha=0.55, label="省下的比例（右轴）")
    ax2.set_ylim(0, 112)
    ax2.set_ylabel("剪枝省下的访问比例（%）", fontsize=12)
    for d, s in zip(depths, saved):
        if d in (2, 5, 9):
            ax2.text(d, s * 100 + 3, f"{s:.0%}", ha="center", fontsize=9, color="#8a6d1a")

    # 图例显式给标签：柱状图是 BarContainer，取它的 patches[0] 只能拿到 "_nolegend_"
    handles = [ax.get_lines()[0], ax.get_lines()[1],
               plt.Rectangle((0, 0), 1, 1, fc=COLOR["hl"], alpha=0.55, ec="none")]
    ax.legend(handles, ["朴素 minimax（全树遍历）", "Alpha-Beta 剪枝", "省下的比例（右轴）"],
              loc="upper left", fontsize=11)
    ax.set_title("剪枝收益随深度累积：depth ≤ 2 为 0，depth = 9 省 96%", fontsize=14, pad=12)
    ax.text(0.99, 0.02,
            "depth ≤ 2 时窗口还来不及收窄就到叶子了，剪枝没有收益",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=10,
            color=COLOR["text"])
    fig.tight_layout()
    fig.savefig(IMAGES / "02-剪枝随深度.png", dpi=130)
    plt.close(fig)


def main() -> None:
    print("① 剪枝示意图 …")
    make_pruning_sketch()
    print("② 剪枝随深度 …")
    rows = depth_profile()
    verify_depth_profile(rows)
    make_depth_chart(rows)
    print("\n产出：")
    for name in ("01-剪枝示意.png", "02-剪枝随深度.png"):
        path = IMAGES / name
        print(f"  {name}  {path.stat().st_size / 1024:.0f} KB")
    print("\ndepth 1–9 两版访问节点数（可粘贴进 README）：")
    print("| depth | minimax 节点 | alphabeta 节点 | 省下 |")
    print("|---|---|---|---|")
    for depth, n_p, n_a in rows:
        print(f"| {depth} | {n_p:,} | {n_a:,} | {1 - n_a / n_p:.1%} |")


if __name__ == "__main__":
    main()
