"""A* 图文素材生成器（供 README「基础篇」引用）。

用途：为 `README.md` 生成图片、流程图与 GIF，并打印手算示例的完整步骤表。

原则：**素材不是手画的，全部由本脚本生成，且与 impl.py 的数字逐项对账**
——真实地图（`demo.make_grid(seed=42)`）上每种策略的扩展数/路径代价，
断言必须与 `impl.solve()` 完全一致，不一致直接报错、不出图。
贪心策略 impl.py 没有对应模式（只按 h 排序），单独断言其教学性质：路径必须次优。

产出（`images/` 目录）：
    01-三个量.png        g（已走）、h（估计剩余）、f = g + h
    02-主循环.png        A* 主循环流程图
    03-四种策略对比.png   真实 21×21 地图上的四种策略搜索范围
    04-搜索动画.gif       Dijkstra vs A* 的逐步扩展过程
    05-手算-四步.png      5×5 小地图的手算示例（四个关键时刻）

运行：
    cd algorithms/p01-search/a-star
    ../../../.venv/bin/python make_teaching_assets.py
"""

from __future__ import annotations

import heapq
import itertools
import numpy as np
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import animation, font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

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


# ---------------------------------------------------------------- ② 主循环


def make_flow() -> None:
    """② 主循环流程图。

    与 `impl.py` 的主循环逐条对应（这正是本图的验收标准）：
    - 初始化（起点入 open、g=0、closed 为空）**在环外**，只执行一次 —— 旧版把它画成
      循环的第一步，还配了标题"重复这四步"，与闭环箭头（回到第 2 步）自相矛盾
    - 循环体是名副其实的四步：取 f 最小 → 查过期堆项 → 判终点 → 移入 closed 并扩展
    - 两步 `closed` 关卡（impl.py 的「过期堆项跳过」与「邻居已 closed 跳过」）必须画出来
      —— 那是手写实现相对于教科书伪代码的差异，也是 README「手写实现要点」讲的东西
    - 三个出口：到达终点（回溯）| open 集空（无解）| 过期堆项（不计扩展，继续取）
    """
    fig, ax = plt.subplots(figsize=(9.8, 13.0))
    ax.set_xlim(-4.6, 18.4)
    ax.set_ylim(0, 22.2)
    ax.axis("off")

    BLUE, YELLOW, GREEN, GRAY = "#eef3ff", "#fff2cc", "#e9f7ef", "#f1f3f5"

    def box(y0: float, y1: float, text: str, color: str = BLUE, fs: float = 13,
            x0: float = 0.0, x1: float = 11.0, ec: str = "#3b5bdb") -> None:
        ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                    boxstyle="round,pad=0.16", fc=color, ec=ec, lw=1.6))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, ha="center", va="center",
                fontsize=fs, linespacing=1.5)

    def diamond(cy: float, text: str, h: float = 1.9) -> None:
        """判定框：菱形，水平跨度 -0.6…11.6，竖直跨度 cy±h/2。"""
        ax.add_patch(Polygon([(5.5, cy + h / 2), (11.6, cy), (5.5, cy - h / 2), (-0.6, cy)],
                             closed=True, fc=YELLOW, ec="#b8860b", lw=1.6))
        ax.text(5.5, cy, text, ha="center", va="center", fontsize=12.5)

    def arrow(x0, y0, x1, y1, head=True, color="#3b5bdb", zorder=4):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1),
                                     arrowstyle="-|>" if head else "-",
                                     mutation_scale=14, color=color, lw=1.8,
                                     shrinkA=0, shrinkB=0, zorder=zorder))

    def polyline(pts, head=True):
        for i, (x0, y0) in enumerate(pts[:-1]):
            arrow(x0, y0, pts[i + 1][0], pts[i + 1][1], head=head and i == len(pts) - 2)

    # ---- 初始化（环外，只执行一次）
    box(19.5, 21.4, "初始化：起点入 open 集，g(起点)=0，closed 为空", GRAY)
    arrow(5.5, 19.4, 5.5, 18.3)

    # ---- 循环体四步 + 两个出口
    box(16.0, 18.2, "① 从 open 集取出 f 最小的点", BLUE, 13.5)
    diamond(12.3, "② 这个点在 closed 里吗？（过期堆项）")
    box(7.5, 9.7, "沿父指针回溯得到路径\n→ 返回最优解", GREEN, 11.5,
        x0=12.3, x1=17.4, ec="#2b8a3e")
    diamond(9.0, "③ 取出的就是终点？")
    box(4.0, 7.0, "④ 移入 closed，扩展它的邻居：\n"
                  "邻居已在 closed → 跳过；\n算出 g 更小 → 松弛并记父指针",
        GREEN, 11.5)
    box(0.6, 2.3, "open 集空 → 无解（返回 path=None，path_cost=inf）", GRAY, 12)

    # ---- 主干
    arrow(5.5, 15.9, 5.5, 13.3)           # ① → ②（停在框外缘）
    arrow(5.5, 11.3, 5.5, 10.0)           # ② →（否）→ ③
    ax.text(5.9, 10.65, "否", fontsize=13, color="#c92a2a", ha="left")
    arrow(5.5, 8.0, 5.5, 7.05)            # ③ →（否）→ ④
    ax.text(5.9, 7.5, "否", fontsize=13, color="#c92a2a", ha="left")
    arrow(5.5, 3.9, 5.5, 2.35)            # ④ → 无解出口（停在框外缘）

    # ---- 出口一：过期堆项 → 回到 ①（不计扩展）
    # 两条回环都从左侧回到 ①，若各自带箭头会形成「两个箭头并排压在框边上」。
    # 故先在框外**合并**，再共用一条入口线 + 一个箭头；合并点取 (-1.6, 15.0)。
    # 外圈横线必须从内圈竖线上方跨过，交叉点用白底断开（标准流程图画法）。
    polyline([(0.0, 4.7), (-3.0, 4.7), (-3.0, 15.0), (-1.6, 15.0)])   # 外圈：④ 左缘 → 合并点
    bridge = Rectangle((-1.79, 14.9), 0.38, 0.20, fc="white", ec="none", zorder=6)
    bridge._is_bridge = True   # 标记：不是流程节点，版式体检跳过
    ax.add_patch(bridge)                                              # 白底断开外圈横线
    polyline([(5.5, 12.3), (-1.6, 12.3)])                             # 内圈：② 左尖 → 下行
    arrow(-1.6, 12.3, -1.6, 15.0, head=False, zorder=7)               # 内圈竖线（压过断口）
    polyline([(-1.6, 15.0), (-0.5, 15.0)], head=True)                 # 合并后共用入口（唯一箭头），离框留白
    ax.text(-3.32, 12.6, "是 → 跳过这个过期堆项（不计扩展）", fontsize=11.5,
            color="#c92a2a", rotation=90, ha="center", va="center")

    # ---- 出口二：取出终点 → 回溯返回
    arrow(11.55, 9.0, 12.25, 9.0, color="#2b8a3e")
    ax.text(12.42, 9.35, "是", fontsize=13, color="#2b8a3e", ha="left")

    # ---- 环回标签
    ax.text(-2.3, 9.6, "回到循环：换下一个 f 最小的点", fontsize=11.5,
            color="#3b5bdb", rotation=90, ha="center", va="center")

    ax.set_title("A* 主循环：初始化只做一次，然后重复这四步直到取出终点",
                 fontsize=15, pad=16)
    fig.tight_layout()
    problems = audit_flow_layout(fig, ax)
    if problems:
        plt.close(fig)
        raise SystemExit("流程图版式体检未通过：\n  - " + "\n  - ".join(problems))
    fig.savefig(IMAGES / "02-主循环.png", dpi=130)
    plt.close(fig)


def audit_flow_layout(fig, ax) -> list[str]:
    """版式体检：流程图的几何错位比数字错误更隐蔽，靠肉眼常常看漏。

    起因：这张图的前几版分别有过「成功出口框与③菱形重叠 0.16」（圆角 boxstyle 的
    pad 会把框向外撑，写代码时以为贴边、实际已压）和「无解框文字溢出 0.04」
    （文本实测宽 11.40 > 框内宽 11.32）——都是量出来才发现、看图看不出的。

    检查三项（都是确定性几何，不依赖渲染后端）：
      1. 框/菱形之间不得重叠
      2. 箭头端点不得穿入框内部
      3. 框内文字不得溢出该框
    返回问题列表；有就打印并让生成器报错，避免坏图被提交。
    """
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

    inv = ax.transData.inverted()

    def extent(bb):
        (x0, y0) = inv.transform((bb.x0, bb.y0))
        (x1, y1) = inv.transform((bb.x1, bb.y1))
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

    nodes, arrows = [], []
    for patch in ax.patches:
        if getattr(patch, "_is_bridge", False):   # 跨线白底，不是节点
            continue
        if isinstance(patch, FancyArrowPatch):
            arrows.append(patch)
        elif isinstance(patch, Polygon):          # 菱形判定框
            nodes.append(("菱形", extent(patch.get_path().get_extents().transformed(ax.transData))))
        elif isinstance(patch, (FancyBboxPatch, Rectangle)):  # 圆角框（含 pad）与普通矩形
            nodes.append(("框", extent(patch.get_path().get_extents().transformed(ax.transData))))

    problems = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            _, (x0, y0, x1, y1) = nodes[i]
            _, (a0, b0, a1, b1) = nodes[j]
            ox = min(x1, a1) - max(x0, a0)
            oy = min(y1, b1) - max(y0, b0)
            if ox > 0.01 and oy > 0.01:
                problems.append(f"节点重叠 {ox:.2f}×{oy:.2f}（y[{y0:.1f},{y1:.1f}] ↔ y[{b0:.1f},{b1:.1f}]）")

    for arrow in arrows:
        for tag, point in zip(("起点", "终点"), arrow._posA_posB):
            px, py = inv.transform(point)
            for kind, (x0, y0, x1, y1) in nodes:
                if x0 + 0.03 < px < x1 - 0.03 and y0 + 0.03 < py < y1 - 0.03:
                    problems.append(f"箭头{tag}({px:.2f},{py:.2f})穿入{kind} y[{y0:.1f},{y1:.1f}]")

    # 像素级复检：几何包含测试曾被 FancyBboxPatch 的未变形路径坑过（判"通过"却实际压框），
    # 故再反查一次渲染结果。做法：把画布上每个「线色」像素反算回数据坐标，落在某个节点
    # 矩形内部（距四边 > 0.30）才算真侵入。这条路径不依赖任何 patch 的路径语义。
    fig.canvas.draw()
    canvas = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].astype(int)
    buf_h, buf_w = canvas.shape[:2]
    png_w, png_h = int(fig.get_size_inches()[0] * 130), int(fig.get_size_inches()[1] * 130)
    sy = png_h / buf_h
    line_px = (canvas[:, :, 2] > 140) & (canvas[:, :, 0] < 130) & (canvas[:, :, 1] < 140)
    ys, xs = np.where(line_px)
    safe = 0.30
    for kind, (x0, y0, x1, y1) in nodes:
        if kind == "菱形":          # 菱形内部是空的，"框套文字"不算侵入
            continue
        cnt = 0
        for col, row in zip(xs[::2], ys[::2]):      # 隔点采样即可，够判侵入
            dx, dy = inv.transform((col, buf_h - row))    # 缓冲行 → 数据 y
            if x0 + safe < dx < x1 - safe and y0 + safe < dy < y1 - safe:
                cnt += 1
        if cnt:
            problems.append(
                f"{kind} y[{y0:.1f},{y1:.1f}] 内部有 {cnt} 个线色采样点"
                f"（距边界 > {safe}）——线画进框里了")

    renderer = fig.canvas.get_renderer()
    for text in ax.texts:
        tx0, ty0, tx1, ty1 = extent(text.get_window_extent(renderer))
        cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
        for kind, (x0, y0, x1, y1) in nodes:
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                if tx0 < x0 - 0.03 or tx1 > x1 + 0.03 or ty0 < y0 - 0.03 or ty1 > y1 + 0.03:
                    problems.append(
                        f"文字溢出{kind} y[{y0:.1f},{y1:.1f}]：「{text.get_text()[:20]}」")
                break
    return problems


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
    make_flow()
    make_compare()
    make_animation()
    make_handcalc()
    print("\n真实地图四策略：")
    for i, (_, _, _, title) in enumerate(REAL_PANELS):
        got = REAL_RESULTS[i]
        print(f"  {title.splitlines()[0]:24s} 扩展 {len(got['expanded']):3d} 格"
              f"  代价 {len(got['path']) - 1}")
    print("✓ 已与 impl.solve 对账；素材输出到", IMAGES)
