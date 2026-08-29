"""启发式搜索两兄弟：贪心最佳优先 / A*。

与 uninformed.py 同构——它们也是**同一个搜索循环**：
    贪心     按 h 最小（只看离终点还有多远）
    A*       按 f = g + h 最小（已付代价 + 剩余估计）

共用一个 `_search(grid, start, goal, weight_g, weight_h)`，
优先级 = weight_g·g + weight_h·h：
    (0, 1) → 贪心最佳优先
    (1, 1) → A*
    (1, 0) → 退化为 UCS/Dijkstra
"""

from dataclasses import dataclass
import heapq
import itertools
from typing import Callable, Optional

from grid_utils import Grid, Pos, neighbors, reconstruct
from uninformed import SearchResult

Heuristic = Callable[[Pos, Pos], float]


def manhattan(a: Pos, b: Pos) -> int:
    """曼哈顿距离：四方向网格上的可采纳启发式。"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _search(grid: Grid, start: Pos, goal: Pos,
            heuristic: Heuristic, weight_g: float, weight_h: float) -> SearchResult:
    """统一启发式搜索：优先级 = weight_g·g + weight_h·h。"""
    counter = itertools.count()
    heap = [(weight_h * heuristic(start, goal), next(counter), start)]
    g_score: dict[Pos, float] = {start: 0.0}
    came_from: dict[Pos, Pos] = {}
    closed: set[Pos] = set()
    expanded = 0

    while heap:
        _, _, node = heapq.heappop(heap)
        if node in closed:
            continue
        closed.add(node)
        expanded += 1
        if node == goal:
            return SearchResult(
                path=reconstruct(came_from, goal),
                nodes_expanded=expanded,
                path_cost=g_score[goal],
                closed=closed,
            )
        for nb in neighbors(grid, node):
            if nb in closed:
                continue
            g2 = g_score[node] + 1
            if g2 < g_score.get(nb, float("inf")):
                g_score[nb] = g2
                came_from[nb] = node
                f = weight_g * g2 + weight_h * heuristic(nb, goal)
                heapq.heappush(heap, (f, next(counter), nb))

    return SearchResult(path=None, nodes_expanded=expanded,
                        path_cost=float("inf"), closed=closed)


def greedy(grid: Grid, start: Pos, goal: Pos,
           heuristic: Heuristic = manhattan) -> SearchResult:
    """贪心最佳优先：只看 h，快但不保证最优。"""
    return _search(grid, start, goal, heuristic, weight_g=0, weight_h=1)


def astar(grid: Grid, start: Pos, goal: Pos,
          heuristic: Heuristic = manhattan) -> SearchResult:
    """A*：g + h，h 可采纳时保证最优。"""
    return _search(grid, start, goal, heuristic, weight_g=1, weight_h=1)


# ---------- 自测 ----------

if __name__ == "__main__":
    from grid_utils import make_grid, render

    grid, start, goal = make_grid(seed=42)
    print(f"地图 {len(grid)}x{len(grid[0])}，start={start}，goal={goal}\n")

    for name, fn in [("贪心", greedy), ("A*", astar)]:
        r = fn(grid, start, goal)
        plen = len(r.path) if r.path else "无解"
        print(f"{name:4} | 路径长度 {plen:>4} | 扩展节点 {r.nodes_expanded:>4} | 代价 {r.path_cost}")

    print("\nA* 结果可视化（# 障碍  * 路径  o 扩展过）:")
    r = astar(grid, start, goal)
    print(render(grid, r.path, r.closed))
