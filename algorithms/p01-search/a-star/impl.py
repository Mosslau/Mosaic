"""A* 启发式搜索 — 手写实现（搜索求解器）

A* 是"带估计的图搜索"：
- open 集：按 f(n) = g(n) + w·h(n) 排序的待扩展节点（g 为实际代价，h 为启发式估计）
- closed 集：已扩展节点（本实现不重开节点）
- 当 h 一致（consistent）且 w = 1 时保证最优；仅"可采纳（admissible）"不足以保证最优——
  closed 不重开的图搜索会把"可采纳但不一致"的 h 变成静默次优解（回归用例见 test_impl.py）
- w 必须 ≥ 1：w = 1 为标准 A*；w > 1 为加权 A*（只保证 w-次优界，不保证最优）

本目录的形态由"寻路"决定，不是 sklearn 估计器，没有 fit/predict：
- impl.py     手写 A*
- baseline.py Dijkstra 对照（h ≡ 0 的 A*，比较启发式的收益）
- demo.py     同一张地图双跑对比 + 平局策略/加权实验

原则：手写核心逻辑，禁止调现成图搜索库（networkx 等）；绘图可用 matplotlib。
"""

import heapq
import itertools
import math
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional


@dataclass
class SearchResult:
    """一次搜索的结果（A* 与 Dijkstra 共用同一结果类型，便于 demo 并排对比）。"""

    path: Optional[list[tuple[int, int]]]  # 从 start 到 goal 的路径（含两端）；无解为 None
    nodes_expanded: int                    # 从 open 集取出的节点数（工作量指标）
    path_cost: float                       # 路径总代价（= len(path) - 1，单步代价恒为 1）
    closed: set = field(default_factory=set)  # 已扩展节点（可视化用）


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """曼哈顿距离启发式（四方向网格上可采纳且一致）。"""
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


def _check_grid(grid: list[list[int]]) -> None:
    """地图形状校验：须是非空矩形。

    不校验的话，后续按 `grid[0]` 取列宽会抛 IndexError——与"越界 start 抛
    ValueError"口径不一致（空网格 / 空行 / 锯齿数组都属入参非法，应统一为 ValueError）。
    """
    if not grid:
        raise ValueError("grid 为空：至少要有一行（例如 [[0]]）")
    if any(len(row) == 0 for row in grid):
        raise ValueError("grid 有空行：每一行至少要有一列")
    widths = {len(row) for row in grid}
    if len(widths) > 1:
        raise ValueError(f"grid 不是矩形：各行长度不一致 {sorted(widths)}")


def _check_passable(grid: list[list[int]], node: tuple[int, int], name: str) -> None:
    """起终点合法性校验：须在界内且可通行。"""
    r, c = node
    if not (0 <= r < len(grid) and 0 <= c < len(grid[0])):
        raise ValueError(f"{name}={node} 越界（地图 {len(grid)}×{len(grid[0])}）")
    if grid[r][c] != 0:
        raise ValueError(f"{name}={node} 落在障碍上")


def solve(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    heuristic: Callable[[tuple[int, int], tuple[int, int]], float] = manhattan,
    *,
    tie_break: Literal["insertion", "large_g"] = "insertion",
    weight: float = 1.0,
) -> SearchResult:
    """A* 寻路。

    参数：
        grid: 二维地图，0=可通行，1=障碍；须为**非空矩形**（空网格、空行、
            锯齿数组一律抛 ValueError，与起终点校验同一口径）
        start / goal: (row, col)，须在界内且可通行
        heuristic: h(n)，默认曼哈顿距离；必须非负且一致（consistent，满足
            h(n) ≤ c(n, n') + h(n')）。本实现不重开节点：仅可采纳但不一致的 h
            可能静默返回次优解（已知局限回归见 test_impl.py）
        tie_break: f 值相同时的平局破解策略——
            "insertion" 按入堆先后（近似广度优先，网格上易退化为全图扩展）；
            "large_g" 优先扩展 g 更大者（即更靠近终点的节点，网格寻路的经典优化）。
            当 f 与 g 都相同时，堆项退化为按节点 (row, col) 字典序比较：结果确定，
            但方向偏置取决于坐标编码；要消除该偏置可给堆项追加单调递增序号
        weight: 启发式权重 w，f = g + w·h；要求是 ≥ 1 的有限数：
            w=1 为标准 A*，w>1 为加权 A*（更快但只保证 w-次优，最优性断言不适用）
    返回：
        SearchResult（path 无解时为 None）
    """
    if tie_break not in ("insertion", "large_g"):
        raise ValueError(f"未知 tie_break={tie_break!r}，可选 'insertion' / 'large_g'")
    try:
        weight_ok = math.isfinite(weight) and weight >= 1
    except TypeError:
        weight_ok = False
    if not weight_ok:
        raise ValueError(
            f"weight 必须是 ≥ 1 的有限数（w=1 标准 A*，w>1 加权 A*），得到 {weight!r}"
        )
    _check_grid(grid)
    _check_passable(grid, start, "start")
    _check_passable(grid, goal, "goal")

    counter = itertools.count()  # insertion 模式的平局序号，保证堆项严格可比

    def tie_key(g: float) -> float:
        # 堆项第二键：f 相同时谁弹出。large_g 取 -g（最小堆 ⇒ g 大者先出）
        return next(counter) if tie_break == "insertion" else -g

    open_heap = [(weight * heuristic(start, goal), tie_key(0.0), start)]
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
                               (g2 + weight * heuristic(nb, goal), tie_key(g2), nb))

    return SearchResult(path=None, nodes_expanded=expanded,
                        path_cost=float("inf"), closed=closed)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：python3 demo.py（需 Python ≥ 3.10）")
