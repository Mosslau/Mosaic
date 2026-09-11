"""A* demo：同一张地图，手写 A* vs Dijkstra 双跑对比。

搜索算法的"对照"是基线算法而非 sklearn：
- 同一张随机障碍地图（固定随机种子，保证起点终点连通）
- 分别跑 impl.solve（A*）与 baseline.dijkstra（Dijkstra）
- 对比 路径长度 / 扩展节点数 / 耗时 —— 启发式 h 的收益由此量化

本文件自带网格工具（make_grid / render），不依赖已移除的共享模块，
保证实验可独立复现。
"""

import random
import time
from collections import deque

from impl import solve
from baseline import dijkstra

Grid = list[list[int]]
Pos = tuple[int, int]


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


def make_grid(rows: int = 21, cols: int = 21, obstacle_ratio: float = 0.3,
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


def main() -> None:
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
    print(f"{'path_len':16} | {len(r_a.path) if r_a.path else 0:>10} | {len(r_d.path) if r_d.path else 0:>10}")
    print(f"{'nodes_expanded':16} | {r_a.nodes_expanded:>10} | {r_d.nodes_expanded:>10}")
    print(f"{'time_ms':16} | {t_a*1000:>10.3f} | {t_d*1000:>10.3f}")

    saved = r_d.nodes_expanded - r_a.nodes_expanded
    print(f"\n启发式收益：少扩展 {saved} 个节点（{saved/r_d.nodes_expanded:.1%}）")

    draw(grid, r_a.path, r_d.path, r_a.closed, r_d.closed)
    # 结论写回本目录 README.md 的「实验结果」一节


if __name__ == "__main__":
    main()
