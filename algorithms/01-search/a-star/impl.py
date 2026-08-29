"""A* 启发式搜索 — 手写实现（搜索求解器）

A* 是"带估计的图搜索"：
- open 集：按 f(n) = g(n) + h(n) 排序的待扩展节点（g 为实际代价，h 为启发式估计）
- closed 集：已扩展节点
- 当 h 可采纳（admissible，不高估真实代价）时，A* 保证找到最优解

本目录的形态由"寻路"决定，不是 sklearn 估计器，没有 fit/predict：
- impl.py     手写 A*
- baseline.py Dijkstra 对照（h ≡ 0 的 A*，比较启发式的收益）
- demo.py     同一张地图双跑对比 + 可视化

原则：手写核心逻辑，禁止调现成图搜索库（networkx 等）；绘图可用 matplotlib。
"""

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class SearchResult:
    """一次搜索的结果（A* 与 Dijkstra 共用同一结果类型，便于 demo 并排对比）。"""

    path: Optional[list[tuple[int, int]]]  # 从 start 到 goal 的路径（含两端）；无解为 None
    nodes_expanded: int                    # 从 open 集取出的节点数（工作量指标）
    path_cost: float                       # 路径总代价
    closed: set = field(default_factory=set)  # 已扩展节点（可视化用）


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """曼哈顿距离启发式（可采纳）。"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _neighbors(grid: list[list[int]], node: tuple[int, int]) -> list[tuple[int, int]]:
    """四方向可通行邻居。"""
    r, c = node
    out = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]) and grid[nr][nc] == 0:
            out.append((nr, nc))
    return out


def solve(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    heuristic: Callable[[tuple[int, int], tuple[int, int]], float] = manhattan,
) -> SearchResult:
    """A* 寻路。

    参数：
        grid: 二维地图，0=可通行，1=障碍
        start / goal: (row, col)，须在界内且可通行
        heuristic: h(n)，默认曼哈顿距离
    返回：
        SearchResult（path 无解时为 None）
    """
    counter = itertools.count()  # 平局破解：f 相同时按插入序，避免节点不可比
    open_heap = [(heuristic(start, goal), next(counter), start)]
    g_score: dict[tuple[int, int], float] = {start: 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    closed: set[tuple[int, int]] = set()
    expanded = 0

    while open_heap:
        _, _, node = heapq.heappop(open_heap)
        if node in closed:
            continue  # 过期堆项：之前以更差的 g 入堆，跳过
        closed.add(node)
        expanded += 1
        if node == goal:
            path = [node]
            while path[-1] in came_from:
                path.append(came_from[path[-1]])
            path.reverse()
            return SearchResult(path=path, nodes_expanded=expanded,
                                path_cost=g_score[goal], closed=closed)
        for nb in _neighbors(grid, node):
            if nb in closed:
                continue
            g2 = g_score[node] + 1
            if g2 < g_score.get(nb, float("inf")):
                g_score[nb] = g2
                came_from[nb] = node
                heapq.heappush(open_heap,
                               (g2 + heuristic(nb, goal), next(counter), nb))

    return SearchResult(path=None, nodes_expanded=expanded,
                        path_cost=float("inf"), closed=closed)


if __name__ == "__main__":
    raise SystemExit("请先完成 solve()，再到 demo.py 跑实验")
