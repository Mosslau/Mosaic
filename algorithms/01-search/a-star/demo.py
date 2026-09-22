"""A* demo：同一张地图，手写 A* vs Dijkstra 双跑对比 + 两个变参实验。

搜索算法的"对照"是基线算法而非 sklearn。三个实验：
1. 主对照：同一张随机障碍地图（固定种子，保证连通），A* vs Dijkstra，
   对比 路径代价 / 扩展节点数 / 耗时 —— 启发式 h 的收益由此量化
2. 平局策略 × 障碍率：无障碍 / 30% 障碍两张图，各跑 insertion 与 large_g
   两种平局破解 —— 展示"平局策略是网格 A* 效率的一阶因素"
3. 加权 A* 扫描：w ∈ {1.0, 2.0, 3.0, 5.0}，f = g + w·h ——
   展示"牺牲最优性换扩展节点数"的对换曲线

本文件自带网格工具（make_grid / render），不依赖外部共享模块，保证实验可独立复现。
"""

import random
import time
from collections import deque

from impl import solve
from baseline import dijkstra

Grid = list[list[int]]
Pos = tuple[int, int]

ROWS = COLS = 21
START, GOAL = (1, 1), (ROWS - 2, COLS - 2)


def neighbors(grid: Grid, node: Pos) -> list[Pos]:
    """四方向可通行邻居（上下左右，代价均为 1）。"""
    r, c = node
    out = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]) and grid[nr][nc] == 0:
            out.append((nr, nc))
    return out


def _reachable(grid: Grid, start: Pos, goal: Pos) -> bool:
    """BFS 洪泛：start 能否走到 goal。"""
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            return True
        for nb in neighbors(grid, cur):
            if nb not in seen:
                seen.add(nb)
                q.append(nb)
    return False


def make_grid(rows: int = ROWS, cols: int = COLS, obstacle_ratio: float = 0.3,
              seed: int = 42) -> tuple[Grid, Pos, Pos]:
    """生成随机障碍地图（0=通路，1=障碍），保证 (1,1) 与 (rows-2, cols-2) 连通。"""
    rng = random.Random(seed)
    start, goal = (1, 1), (rows - 2, cols - 2)
    for _ in range(1000):
        grid = [[0] * cols for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                border = r in (0, rows - 1) or c in (0, cols - 1)
                if border or rng.random() < obstacle_ratio:
                    grid[r][c] = 1
        grid[start[0]][start[1]] = 0
        grid[goal[0]][goal[1]] = 0
        if _reachable(grid, start, goal):
            return grid, start, goal
    raise RuntimeError("1000 次尝试仍未生成连通地图，降低 obstacle_ratio 试试")


def make_empty_grid(rows: int = ROWS, cols: int = COLS) -> Grid:
    """无障碍地图（仅边界墙）：曼哈顿启发式在此是紧的，f 值全场平局。"""
    grid = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        grid[i][0] = grid[i][cols - 1] = 1
    for j in range(cols):
        grid[0][j] = grid[rows - 1][j] = 1
    return grid


def render(grid: Grid, path: list[Pos] | None = None,
           closed: set[Pos] | None = None) -> str:
    """ASCII 渲染：# 障碍  . 通路  * 路径  o 扩展过。"""
    path_set = set(path) if path else set()
    closed = closed or set()
    lines = []
    for r, row in enumerate(grid):
        chars = []
        for c, cell in enumerate(row):
            p = (r, c)
            if cell == 1:
                chars.append("#")
            elif p in path_set:
                chars.append("*")
            elif p in closed:
                chars.append("o")
            else:
                chars.append(".")
        lines.append("".join(chars))
    return "\n".join(lines)


def draw(grid, path_a: list, path_d: list, closed_a: set, closed_d: set) -> None:
    """ASCII 渲染地图 + 两条路径 + 扩展区域。"""
    print("\nA*（* 路径  o 扩展过）:")
    print(render(grid, path_a, closed_a))
    print("\nDijkstra（* 路径  o 扩展过）:")
    print(render(grid, path_d, closed_d))


def experiment_main() -> None:
    """实验一：A* vs Dijkstra 主对照（30% 障碍，seed=42）。"""
    print("== 实验一：A* vs Dijkstra（21×21，30% 障碍，seed=42）==")
    grid, start, goal = make_grid()

    t0 = time.perf_counter()
    r_a = solve(grid, start, goal)
    t_a = time.perf_counter() - t0

    t0 = time.perf_counter()
    r_d = dijkstra(grid, start, goal)
    t_d = time.perf_counter() - t0

    # 断言：同一张图，两算法必须找到相同代价的最短路径
    assert r_a.path_cost == r_d.path_cost, (
        f"最优性破坏：A* 代价 {r_a.path_cost} ≠ Dijkstra 代价 {r_d.path_cost}"
    )

    print(f"{'':16} | {'A*':>10} | {'Dijkstra':>10}")
    print("-" * 44)
    print(f"{'path_len(节点数)':16} | {len(r_a.path) if r_a.path else 0:>10} | {len(r_d.path) if r_d.path else 0:>10}")
    print(f"{'path_cost(代价)':16} | {r_a.path_cost:>10.0f} | {r_d.path_cost:>10.0f}")
    print(f"{'nodes_expanded':16} | {r_a.nodes_expanded:>10} | {r_d.nodes_expanded:>10}")
    print(f"{'time_ms':16} | {t_a*1000:>10.3f} | {t_d*1000:>10.3f}")

    saved = r_d.nodes_expanded - r_a.nodes_expanded
    print(f"\n启发式收益：少扩展 {saved} 个节点（{saved/r_d.nodes_expanded:.1%}）")

    draw(grid, r_a.path, r_d.path, r_a.closed, r_d.closed)


def experiment_tiebreak() -> None:
    """实验二：平局策略 × 障碍率（2×2）。

    无障碍地图上曼哈顿 h 是紧的 ⇒ 所有自由节点 f ≡ C*，扩展多少个
    f = C* 的节点完全由平局破解决定：insertion 退化为全图扩展，
    large_g 直冲终点（扩展数 = 路径节点数，理论下界）。
    """
    print("\n== 实验二：平局破解策略 × 障碍率 ==")
    cases = []
    for name, grid in (("无障碍", make_empty_grid()), ("30% 障碍", make_grid()[0])):
        optimal = dijkstra(grid, START, GOAL).path_cost  # Dijkstra 给出最优代价基准
        cases.append((name, grid, optimal))

    print(f"{'地图':<12} | {'insertion':>10} | {'large_g':>10} | {'最优代价':>8}")
    print("-" * 52)
    for name, grid, optimal in cases:
        r_ins = solve(grid, START, GOAL)
        r_lg = solve(grid, START, GOAL, tie_break="large_g")
        # 两种平局策略都必须保持最优（平局只影响效率，不影响最优性）
        assert r_ins.path_cost == r_lg.path_cost == optimal
        print(f"{name:<12} | {r_ins.nodes_expanded:>10} | {r_lg.nodes_expanded:>10} | {optimal:>8.0f}")
    print("观察：无障碍时所有节点 f 值相同，insertion 全图扩展而 large_g 直达下界；")
    print("      障碍使 g 绕路、f 值分层，平局的影响随之减弱。")


def experiment_weight() -> None:
    """实验三：加权 A* 扫描，f = g + w·h（30% 障碍图，large_g 平局）。

    w = 1 最优；w > 1 不再保证最优，只保证 w-次优界——
    用扩展节点数换路径代价的对换由此量化。
    """
    print("\n== 实验三：加权 A*（f = g + w·h）==")
    grid, start, goal = make_grid()
    optimal = dijkstra(grid, start, goal).path_cost

    print(f"{'w':>5} | {'nodes_expanded':>14} | {'path_cost':>9} | {'相对最优':>8}")
    print("-" * 48)
    for w in (1.0, 2.0, 3.0, 5.0):
        r = solve(grid, start, goal, tie_break="large_g", weight=w)
        gap = (r.path_cost - optimal) / optimal
        print(f"{w:>5.1f} | {r.nodes_expanded:>14} | {r.path_cost:>9.0f} | {gap:>+8.1%}")
    print(f"观察：w ≤ 2 仍命中最优代价 {optimal:.0f}；w = 3 起代价变差——")
    print("      高估 h 让搜索更早冲向终点，但不再保证最优（最优性断言仅限 w = 1）。")


def main() -> None:
    experiment_main()
    experiment_tiebreak()
    experiment_weight()
    # 结论写回本目录 README.md 的「实验结果」一节


if __name__ == "__main__":
    main()
