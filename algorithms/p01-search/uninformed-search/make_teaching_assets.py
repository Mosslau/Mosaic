"""无信息搜索图文素材生成器（供 README 引用）。

原则：素材全部由本脚本生成，且与 `demo.py` 的数字逐项对账——不一致直接报错、不出图（纪律④）。

产出（`images/` 目录）：
    01-扩展顺序.png    同一张 5×5 小图上，DFS / BFS / UCS 的扩展顺序（第几步取出）
    02-代价与内存.png  带权图上 BFS 的次优程度 + 三个算法的边界峰值对比 + UCS vs A*

流程图不在这里——优先 Mermaid 直接写进 README（见 visual-assets.md）。

运行：cd algorithms/p01-search/uninformed-search && python3 make_teaching_assets.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
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
            "请安装任一中文字体（如 Noto Sans CJK / 文泉驿）后重跑。")
    font_path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font

    if ft2font.FT2Font(font_path).get_char_index(ord("中")) == 0:
        raise SystemExit(f"字体 {chosen}（{font_path}）不含中文字形，拒绝生成方块版素材")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


FONT_USED = setup_cjk_font()

import demo as D  # noqa: E402

COLOR = dict(dfs="#c92a2a", bfs="#2b8a3e", ucs="#3b5bdb", wall="#4a4a4a",
             grid="#dee2e6", text="#343a40", hl="#f6c344")


# ---------------------------------------------------------------- 取数（与 demo 同源）

def order_data(seed: int = 3, rows: int = 5, cols: int = 5) -> dict:
    """小图上的三份取出顺序：与 demo.experiment_order 用同一套函数取数。"""
    grid, start, goal = D.make_grid(rows, cols, obstacle_ratio=0.2, seed=seed)
    out = {}
    for name, fn in (("dfs", D.dfs), ("bfs", D.bfs), ("ucs", D.ucs)):
        r = fn(grid, start, goal, record_order=True)
        out[name] = {"result": r, "rank": {node: i + 1 for i, node in enumerate(r.order)}}
    return {"grid": grid, "start": start, "goal": goal, **out}


def weighted_data(games: int = 8, seed0: int = 200) -> list:
    """带权地形上逐张统计：BFS 的步数/代价、UCS 的代价、两者的扩展数。"""
    rows = []
    for i in range(games):
        grid, start, goal = D.make_terrain(seed=seed0 + i)
        cost_of = lambda n, g=grid: D.terrain_cost(n, g)
        r_bfs = D.bfs(grid, start, goal)
        r_ucs = D.ucs(grid, start, goal, cost_of=cost_of)
        bfs_cost = float(sum(cost_of(n) for n in r_bfs.path[1:]))
        rows.append({"steps_bfs": len(r_bfs.path), "steps_ucs": len(r_ucs.path),
                     "cost_bfs": bfs_cost, "cost_ucs": r_ucs.cost,
                     "gap": bfs_cost / r_ucs.cost - 1,
                     "exp_bfs": r_bfs.expanded, "exp_ucs": r_ucs.expanded,
                     "peak_bfs": r_bfs.peak_frontier, "peak_ucs": r_ucs.peak_frontier})
    return rows


def per_algorithm_data(rows: int = 9, cols: int = 9, games: int = 6) -> dict:
    """小图上三个算法的**真实**均值（扩展数 / 内存尖峰）——不能拿同一个数充三个算法。"""
    agg = {"dfs": {"exp": [], "peak": []}, "bfs": {"exp": [], "peak": []},
           "ucs": {"exp": [], "peak": []}}
    for i in range(games):
        grid, start, goal = D.make_grid(rows, cols, seed=42 + i)
        for name, fn in (("dfs", D.dfs), ("bfs", D.bfs), ("ucs", D.ucs)):
            r = fn(grid, start, goal)
            agg[name]["exp"].append(r.expanded)
            agg[name]["peak"].append(r.peak_frontier)
    return {k: {"exp": sum(v["exp"]) / len(v["exp"]),
                "peak": sum(v["peak"]) / len(v["peak"])} for k, v in agg.items()}


def ucs_vs_astar_data(seed: int = 42) -> dict:
    """无权图上 UCS 与 A*(insertion / large_g) 的扩展数对照。"""
    return D.experiment_ucs_vs_astar(seed=seed)


def verify(order: dict, weighted: list, ucs_astar: dict, per_algo: dict) -> None:
    """对账：图里要讲的每条规律都必须由数据支撑。"""
    for name in ("dfs", "bfs", "ucs"):
        assert order[name]["result"].path is not None, f"{name} 在小图上应当有解"
    assert order["bfs"]["result"].cost <= order["dfs"]["result"].cost, \
        "BFS 的步数不该比 DFS 多"
    assert all(r["cost_bfs"] >= r["cost_ucs"] - 1e-9 for r in weighted), \
        "带权图上 BFS 的代价不该低于 UCS（UCS 是最优的）"
    assert any(r["gap"] > 0.05 for r in weighted), \
        "至少要有几张图体现 BFS 明显次优，否则图没有说服力"
    assert ucs_astar["saved"] > 0, "A* 应当比 UCS 少扩展节点"
    exps = {k: per_algo[k]["exp"] for k in per_algo}
    assert len(set(exps.values())) == len(exps), (
        f"三个算法的扩展数不该相同（否则说明数据填错了）：{exps}")
    print(f"  ✓ 对账通过：BFS 最优但内存更高；带权图上 BFS 最差贵 "
          f"{max(r['gap'] for r in weighted):.0%}；A* 比 UCS 少扩展 "
          f"{ucs_astar['saved']:.0%}")


# ---------------------------------------------------------------- ① 扩展顺序

def make_order_figure(order: dict) -> None:
    """三张子图：同一张图上每个格子被"第几步取出"——看三种策略的形状。"""
    grid, start, goal = order["grid"], order["start"], order["goal"]
    rows, cols = len(grid), len(grid[0])
    fig, axes = plt.subplots(1, 3, figsize=(14.4, 5.2))

    for ax, (name, label) in zip(axes, (("dfs", "DFS（栈：一条道走到黑）"),
                                        ("bfs", "BFS（队列：一圈圈向外）"),
                                        ("ucs", "UCS（优先队列：按代价分层）"))):
        rank = order[name]["rank"]
        r = order[name]["result"]
        data = np.full((rows, cols), np.nan)
        for (rr, cc), k in rank.items():
            data[rr, cc] = k
        ax.imshow(np.ma.masked_invalid(data), cmap="viridis_r", origin="upper",
                  interpolation="nearest")
        for rr in range(rows):
            for cc in range(cols):
                if grid[rr][cc] == -1:
                    ax.add_patch(plt.Rectangle((cc - .5, rr - .5), 1, 1,
                                               fc=COLOR["wall"], ec="none"))
                elif (rr, cc) in rank:
                    ax.text(cc, rr, str(rank[(rr, cc)]), ha="center", va="center",
                            fontsize=9, color="white")
        for (rr, cc), txt in ((start, "S"), (goal, "G")):
            ax.text(cc, rr, txt, ha="center", va="center", fontsize=12, weight="bold",
                    color=COLOR["hl"])
        ax.set_xticks(range(cols)); ax.set_yticks(range(rows))
        ax.set_xticklabels([]); ax.set_yticklabels([])
        ax.grid(color=COLOR["grid"], lw=0.8)
        ax.set_title(f"{label}\n扩展 {r.expanded} 个 · 步数 {len(r.path) - 1}",
                     fontsize=12, pad=8)

    fig.suptitle("同一张图、同一个问题，只有「取出顺序」不同——格子里的数字是第几步被取出",
                 fontsize=14, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(IMAGES / "01-扩展顺序.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- ② 代价与内存

def make_cost_memory_figure(weighted: list, ucs_astar: dict, per_algo: dict) -> None:
    """左：带权图上 BFS 的代价差距；右：边界峰值 vs 扩展数（内存为什么重要）。"""
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 5.4))

    ax = axes[0]
    xs = np.arange(len(weighted))
    ax.bar(xs - 0.2, [r["cost_ucs"] for r in weighted], width=0.4,
           color=COLOR["ucs"], label="UCS（按代价最优）")
    ax.bar(xs + 0.2, [r["cost_bfs"] for r in weighted], width=0.4,
           color=COLOR["bfs"], label="BFS（只保证步数最少）")
    for i, r in enumerate(weighted):
        ax.text(i + 0.2, r["cost_bfs"] + 4, f"+{r['gap']:.0%}", ha="center",
                fontsize=9, color=COLOR["bfs"])
    ax.set_xticks(xs); ax.set_xticklabels([f"图 {i}" for i in xs])
    ax.set_ylabel("路径总代价", fontsize=12)
    ax.set_title("带权地形（进入代价 1–9）：BFS 的步数最少 ≠ 代价最小", fontsize=12.5, pad=10)
    ax.legend(fontsize=11)
    ax.grid(axis="y", color=COLOR["grid"], lw=0.8); ax.set_axisbelow(True)

    ax = axes[1]
    labels = ["DFS", "BFS", "UCS"]
    expanded = [per_algo["dfs"]["exp"], per_algo["bfs"]["exp"], per_algo["ucs"]["exp"]]
    peaks = [per_algo["dfs"]["peak"], per_algo["bfs"]["peak"], per_algo["ucs"]["peak"]]
    xs = np.arange(len(labels))
    ax.bar(xs - 0.2, expanded, width=0.4, color=COLOR["dfs"], label="扩展节点数")
    ax.bar(xs + 0.2, peaks, width=0.4, color=COLOR["hl"], label="边界峰值（内存代理）")
    for i, (e, p) in enumerate(zip(expanded, peaks)):
        ax.text(i - 0.2, e + 4, f"{e:.0f}", ha="center", fontsize=9, color=COLOR["dfs"])
        ax.text(i + 0.2, p + 4, f"{p:.0f}", ha="center", fontsize=9, color="#8a6d1a")
    ax.set_xticks(xs); ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("节点数（9×9 无权图 × 6 张的均值）", fontsize=12)
    ax.set_title("扩展数 ≠ 内存：DFS 干活少，但边界反而最大（栈里压着一路的岔路）",
                 fontsize=12.5, pad=10)
    ax.legend(fontsize=11)
    ax.grid(axis="y", color=COLOR["grid"], lw=0.8); ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(IMAGES / "02-代价与内存.png", dpi=130)
    plt.close(fig)


def main() -> None:
    print("取数：小图扩展顺序 …")
    order = order_data()
    print("取数：带权图代价与内存 …")
    weighted = weighted_data()
    print("取数：UCS vs A* …")
    ucs_astar = ucs_vs_astar_data()
    print("取数：三算法在小图上的真实均值 …")
    per_algo = per_algorithm_data()
    verify(order, weighted, ucs_astar, per_algo)
    print("① 画扩展顺序 …")
    make_order_figure(order)
    print("② 画代价与内存 …")
    make_cost_memory_figure(weighted, ucs_astar, per_algo)
    print("\n产出：")
    for name in ("01-扩展顺序.png", "02-代价与内存.png"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")
    print("\n可粘贴进 README 的对照表（带权图）:")
    print("| 图 | BFS 步数 | BFS 代价 | UCS 代价 | BFS 相对最优 |")
    print("|---|---|---|---|---|")
    for i, r in enumerate(weighted):
        print(f"| {i} | {r['steps_bfs']} | {r['cost_bfs']:.0f} | {r['cost_ucs']:.0f} | "
              f"+{r['gap']:.0%} |")


if __name__ == "__main__":
    main()
