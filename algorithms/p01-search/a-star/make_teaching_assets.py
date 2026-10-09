"""A* 图文素材生成器（供 README「基础篇」引用）。

用途：为 `README.md` 生成概念图 / 对比图 / 动画，并打印手算示例的完整步骤表。

原则：**素材不是手画的，全部由本脚本生成，且与 impl.py 的数字逐项对账**
——真实地图（`demo.make_grid(seed=42)`）上每种策略的扩展数/路径代价，
断言必须与 `impl.solve()` 完全一致，不一致直接报错、不出图。
贪心策略 impl.py 没有对应模式（只按 h 排序），单独断言其教学性质：路径必须次优。

产出（`images/` 目录）：
    01-三个量.png        g（已走）、h（估计剩余）、f = g + h
    03-四种策略对比.png   真实 21×21 地图上的四种策略搜索范围
    04-搜索动画.gif       Dijkstra vs A* 的逐步扩展过程
    05-手算-四步.png      5×5 小地图的手算示例（四个关键时刻）

**主循环流程图不在这里生成**：它改用 Mermaid 直接写在 README「算法主循环」节里
（文本可 diff、可搜索、零体积，见 mindspring-lab 规范「Mermaid 优先」）。

运行：
    cd algorithms/p01-search/a-star
    ../../../.venv/bin/python make_teaching_assets.py
"""

from __future__ import annotations

import heapq
import itertools
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import animation, font_manager
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from demo import make_grid  # noqa: E402
from impl import manhattan, solve  # noqa: E402

IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)

def setup_cjk_font() -> str:
    """注册一个**确实含中文字形**的字体，返回字体名；找不到就报错，绝不画方块。

    为什么不用「硬编码 Linux 字体路径 + exists() 判断」：那条路在 macOS / Windows 上
    一个候选都命不中，循环静默跳过、font.family 保持默认 DejaVu Sans（无中文字形），
    于是**整张图的中文变成方框**——matplotlib 只在 stderr 发 UserWarning，退出码仍是 0，
    素材会被静默替换成方块版。本机 macOS 实测就是这个症状。

    改为「按字体名查 fontManager + FreeType 字形校验」：
    - 跨平台：matplotlib 会把系统字体扫进 fontManager，按名查无需知道安装路径
    - 可证伪：直接问 FreeType 有没有「中」的字形，查不到就 SystemExit
    """
    cjk_names = (
        "Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC", "Source Han Sans CN",
        "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",           # Linux
        "Hiragino Sans GB", "PingFang SC", "Heiti TC",
        "STHeiti", "Songti SC", "Arial Unicode MS",           # macOS
        "Microsoft YaHei", "SimHei",                          # Windows
    )
    # 也保留显式路径候选（部分环境不把字体交给 fontManager 扫描）
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

Color = dict(
    wall="#4a4a4a",
    closed="#f6c344",
    open="#8fb8f0",
    path="#1f4fd8",
    start="#0b6b0b",
    goal="#00a0a0",
    text="#1b1b1b",
)


# ---------------------------------------------------------------- 搜索（带轨迹）


def traced(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    kind: str = "astar",
    weight: float = 1.0,
    large_g: bool = False,
    record: bool = False,
) -> dict:
    """与 impl.solve 同一套规则的可观察版本；kind: dijkstra | greedy | astar。"""
    rows, cols = len(grid), len(grid[0])

    def neighbors(node: tuple[int, int]):
        r, c = node
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p = (r + dr, c + dc)
            if 0 <= p[0] < rows and 0 <= p[1] < cols and grid[p[0]][p[1]] == 0:
                yield p

    order = itertools.count()
    heap: list[tuple[float, float, tuple[int, int]]] = []
    g = {start: 0}
    came: dict[tuple[int, int], tuple[int, int]] = {}
    closed: set[tuple[int, int]] = set()
    expanded: list[tuple[int, int]] = []
    steps: list[dict] = []

    def h(n: tuple[int, int]) -> int:
        return manhattan(n, goal)

    def key(n: tuple[int, int]) -> float:
        if kind == "dijkstra":
            return 0.0
        if kind == "greedy":
            return float(h(n))
        return g[n] + weight * h(n)

    def tie(n: tuple[int, int]) -> float:
        return -g[n] if large_g else next(order)

    heapq.heappush(heap, (key(start), tie(start), start))
    while heap:
        _, _, node = heapq.heappop(heap)
        if node in closed:
            continue
        closed.add(node)
        expanded.append(node)
        if node == goal:
            if record:
                pending = sorted(
                    {(p, key(p)) for _, _, p in heap if p not in closed},
                    key=lambda t: (t[1], t[0]),
                )
                steps.append(
                    dict(node=node, g=g[node], h=h(node), f=key(node),
                         closed=len(closed), open_top=pending[:4], done=True)
                )
            break
        for p in neighbors(node):
            ng = g[node] + 1
            if p not in g or ng < g[p]:
                g[p] = ng
                came[p] = node
                heapq.heappush(heap, (key(p), tie(p), p))
        if record:
            pending = []
            seen: set[tuple[int, int]] = set()
            for _, _, p in sorted(heap, key=lambda t: (t[0], t[1])):
                if p not in closed and p not in seen:
                    seen.add(p)
                    pending.append((p, key(p)))
            steps.append(
                dict(node=node, g=g[node], h=h(node), f=key(node),
                     closed=len(closed), open_top=pending[:4], done=False)
            )

    path: list[tuple[int, int]] = []
    if goal in came or goal == start:
        n = goal
        while n != start:
            path.append(n)
            n = came[n]
        path.append(start)
        path.reverse()
    return dict(path=path, expanded=expanded, steps=steps, g=g)


# ---------------------------------------------------------------- 通用画格子


def draw_grid(ax, grid, marks: dict | None = None, label=None) -> None:
    """marks: {(r,c): (文字, 底色)}；None 表示只画墙。"""
    rows, cols = len(grid), len(grid[0])
    for r in range(rows):
        for c in range(cols):
            fc = Color["wall"] if grid[r][c] == 1 else "#ffffff"
            text, fill = (marks or {}).get((r, c), ("", None))
            if fill:
                fc = fill
            ax.add_patch(Rectangle((c, r), 1, 1, fc=fc, ec="#cccccc", lw=0.8))
            if text:
                ax.text(c + 0.5, r + 0.5, text, ha="center", va="center",
                        fontsize=8.5, color=Color["text"], zorder=5)
    ax.set_xlim(0, cols)
    ax.set_ylim(rows, 0)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    if label:
        ax.set_title(label, fontsize=12)


# ---------------------------------------------------------------- ① 三个量


def make_concept() -> None:
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.add_patch(Rectangle((0.6, 1.35), 4.4, 0.9, fc="#8fb8f0", ec="#3b5bdb"))
    ax.add_patch(Rectangle((5.0, 1.35), 3.2, 0.9, fc="#f6c344", ec="#b8860b"))
    ax.text(2.8, 1.8, "g：已经走了多远（真实、已知）", ha="center", va="center",
            fontsize=13)
    ax.text(6.6, 1.8, "h：估计还剩多远", ha="center", va="center", fontsize=13)
    ax.annotate("", xy=(9.0, 1.8), xytext=(8.4, 1.8),
                arrowprops=dict(arrowstyle="-|>", lw=2, color="#444444"))
    ax.text(9.2, 1.8, "终点", va="center", fontsize=12)
    ax.text(0.6, 2.5, "起点", fontsize=12)
    ax.text(5.0, 0.7, "总分 f = g + h —— 每次优先处理总分最小的点",
            ha="center", fontsize=14, color="#c92a2a")
    ax.set_title("A* 只做一件事：给每个候选点算一个总分", fontsize=15, pad=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-三个量.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- ③④ 真实地图

REAL_GRID, REAL_START, REAL_GOAL = make_grid(seed=42)

REAL_PANELS = [
    ("dijkstra", 1.0, False, "① Dijkstra（h≡0）\n只认已走距离：全向扩散"),
    ("greedy", 1.0, False, "② 贪心（只看 h）\n朝终点冲：快，但不保证最优"),
    # 面板③④标出 large_g：A* 的扩展数依赖平局策略（insertion 214 / large_g 199），
    # 不标的话读者拿这张图（199）对进阶篇实验一表格的 A*(insertion) 列（214）会以为对不上。
    ("astar", 1.0, True, "③ A*（f = g + h，large_g 平局）\n同样的最优解，扩展更少"),
    ("astar", 3.0, True, "④ 加权 A*（w=3，large_g 平局）\n更快，但代价让位于速度"),
]

REAL_RESULTS = {
    i: traced(REAL_GRID, REAL_START, REAL_GOAL, kind, w, lg)
    for i, (kind, w, lg, _) in enumerate(REAL_PANELS)
}


def verify_real_map() -> None:
    """教学素材与 impl.solve 对账。"""
    refs = [
        (0, solve(REAL_GRID, REAL_START, REAL_GOAL, heuristic=lambda a, b: 0)),
        (2, solve(REAL_GRID, REAL_START, REAL_GOAL, tie_break="large_g")),
        (3, solve(REAL_GRID, REAL_START, REAL_GOAL, tie_break="large_g", weight=3.0)),
    ]
    for i, ref in refs:
        got = REAL_RESULTS[i]
        assert len(got["expanded"]) == ref.nodes_expanded, (
            f"面板 {i}: 扩展数 {len(got['expanded'])} != impl {ref.nodes_expanded}"
        )
        assert len(got["path"]) - 1 == ref.path_cost, (
            f"面板 {i}: 代价 {len(got['path']) - 1} != impl {ref.path_cost}"
        )
    # 贪心（面板 1）：impl.py 无该模式，断言教学前提——扩展更少但路径次优
    greedy_path, greedy_expanded = REAL_RESULTS[1]["path"], REAL_RESULTS[1]["expanded"]
    optimal = solve(REAL_GRID, REAL_START, REAL_GOAL, heuristic=lambda a, b: 0).path_cost
    assert len(greedy_path) - 1 > optimal, (
        f"贪心在本图应次优（教学前提）：代价 {len(greedy_path) - 1} 应 > 最优 {optimal}"
    )
    assert len(greedy_expanded) < len(REAL_RESULTS[0]["expanded"]), (
        "贪心在本图应比 Dijkstra 少扩展（教学前提）"
    )


def paint_real(ax, index: int, reveal: int | None = None) -> None:
    grid = REAL_GRID
    rows, cols = len(grid), len(grid[0])
    result = REAL_RESULTS[index]
    path, expanded = result["path"], result["expanded"]
    shown = expanded if reveal is None else expanded[:reveal]
    order_of = {node: i for i, node in enumerate(expanded)}
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                fc = Color["wall"]
            elif (r, c) in order_of and order_of[(r, c)] < len(shown):
                k = order_of[(r, c)] / max(1, len(expanded) - 1)
                fc = (1.0, 0.85 - 0.65 * k, 0.25 - 0.15 * k)
            else:
                fc = "#ffffff"
            ax.add_patch(Rectangle((c, r), 1, 1, fc=fc, ec="none"))
    if reveal is None or reveal >= len(expanded):
        ax.plot([c + 0.5 for _, c in path], [r + 0.5 for r, _ in path], "-",
                color=Color["path"], lw=2.4, zorder=6)
    ax.scatter([REAL_START[1] + 0.5], [REAL_START[0] + 0.5], marker="o", s=90,
               facecolors="none", edgecolors=Color["start"], lw=2.2)
    ax.scatter([REAL_GOAL[1] + 0.5], [REAL_GOAL[0] + 0.5], marker="*", s=140,
               c=Color["goal"], edgecolors="#004d4d", lw=1)
    ax.set_xlim(-1, cols + 1)
    ax.set_ylim(rows + 1, -1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def make_compare() -> None:
    fig, axes = plt.subplots(1, 4, figsize=(19, 6.4))
    for i, (ax, (_, _, _, title)) in enumerate(zip(axes, REAL_PANELS)):
        paint_real(ax, i)
        path, expanded = REAL_RESULTS[i]["path"], REAL_RESULTS[i]["expanded"]
        ax.set_title(f"{title}\n扩展 {len(expanded)} 格 · 路径代价 {len(path) - 1}",
                     fontsize=13)
    fig.suptitle("同一张地图（21×21，30% 障碍，种子 42）：颜色 = 处理先后，蓝线 = 最终路径",
                 fontsize=17)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(IMAGES / "03-四种策略对比.png", dpi=110)
    plt.close(fig)


def make_animation() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 7.0))
    picks = [0, 2]
    total = max(len(REAL_RESULTS[i]["expanded"]) for i in picks)
    frames = list(range(0, total + 6, 6))

    def update(k: int):
        for ax, i in zip(axes, picks):
            ax.clear()
            paint_real(ax, i, reveal=k)
            n = min(k, len(REAL_RESULTS[i]["expanded"]))
            ax.set_title(f"{REAL_PANELS[i][3]}\n已处理 {n} 格", fontsize=13)
        return []

    anim = animation.FuncAnimation(fig, update, frames=frames, interval=120)
    anim.save(IMAGES / "04-搜索动画.gif", writer=animation.PillowWriter(fps=8))
    plt.close(fig)


# ---------------------------------------------------------------- ⑤ 手算示例

HAND_GRID = [
    [0, 0, 0, 0, 0],
    [1, 1, 1, 1, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 1, 0, 0],
    [0, 0, 0, 0, 0],
]
HAND_START, HAND_GOAL = (0, 0), (4, 4)


def make_handcalc() -> None:
    result = traced(HAND_GRID, HAND_START, HAND_GOAL, "astar", record=True)
    steps = result["steps"]
    order_of = {node: i for i, node in enumerate(result["expanded"])}
    picks = [0, 3, 6, len(steps) - 1]
    picks = sorted({min(p, len(steps) - 1) for p in picks})

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 11.5))
    for ax, idx in zip(axes.ravel(), picks):
        step = steps[idx]
        cut = order_of.get(step["node"], -1) + 1
        marks = {}
        for node, i in order_of.items():
            if i > cut:
                continue
            r, c = node
            g = result["g"][node]
            h = manhattan(node, HAND_GOAL)
            fill = Color["closed"] if i < cut else "#ffd9d9"
            marks[(r, c)] = (f"{g}+{h}={g + h}", fill)
        pending = "  ".join(f"{p} f={int(f)}" for p, f in step["open_top"][:3])
        title = (
            f"第 {idx + 1} 步：取出 {step['node']}｜g={step['g']} "
            f"h={step['h']} f={int(step['f'])}"
            + ("（终点！）" if step["done"] else "")
            + f"\n待办清单前 3：{pending or '（空）'}"
        )
        draw_grid(ax, HAND_GRID, marks, label=title)
        if step["done"]:
            ax.plot([c + 0.5 for _, c in result["path"]],
                    [r + 0.5 for r, _ in result["path"]],
                    "-", color=Color["path"], lw=2.6)

    fig.suptitle("手算示例：5×5 地图，格子里的 3+3=6 就是 g+h=f（红色 = 刚刚取出的点）",
                 fontsize=14, y=0.975)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(IMAGES / "05-手算-四步.png", dpi=120)
    plt.close(fig)

    print("手算示例完整步骤（可直接粘进文档）：")
    print("| 步骤 | 取出 | g | h | f | 处理后待办清单（前 3） |")
    print("|---|---|---|---|---|---|")
    for i, step in enumerate(steps):
        pending = "、".join(f"{p} f={int(f)}" for p, f in step["open_top"][:3]) or "（空）"
        flag = "（终点）" if step["done"] else ""
        print(f"| {i + 1} | {step['node']}{flag} | {step['g']} | {step['h']} "
              f"| {int(step['f'])} | {pending} |")
    path = result["path"]
    print(f"路径：{path}，代价 {len(path) - 1}，共扩展 {len(result['expanded'])} 格")


if __name__ == "__main__":
    verify_real_map()
    make_concept()
    make_compare()
    make_animation()
    make_handcalc()
    print("\n真实地图四策略：")
    for i, (_, _, _, title) in enumerate(REAL_PANELS):
        got = REAL_RESULTS[i]
        print(f"  {title.splitlines()[0]:24s} 扩展 {len(got['expanded']):3d} 格"
              f"  代价 {len(got['path']) - 1}")
    print("✓ 已与 impl.solve 对账；素材输出到", IMAGES)
