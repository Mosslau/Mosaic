"""第 4 题参考解：A* 扩展到八邻域（对角代价 √2）。

要点：
- 八方向移动：直走代价 1，斜走代价 √2；对角不允许"贴角穿越"（两个正交邻格都要空）
- 启发式换成 octile distance（八邻域下不高估；曼哈顿会高估，不再可用）
- 与 Dijkstra（h ≡ 0）在随机地图上对拍：路径代价必须逐张一致

运行：
    cd algorithms/p01-search/a-star/exercises
    ../../../../.venv/bin/python sol-04-八邻域.py
"""

from __future__ import annotations

import heapq
import itertools
import math
import random
from collections import deque

DIAG = math.sqrt(2)
EPS = 1e-9

STRAIGHT = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAGONAL = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def octile(a: tuple[int, int], b: tuple[int, int]) -> float:
    """八邻域的精确空地图距离：先斜走 min(dr,dc) 步，再直走剩下的。"""
    dr, dc = abs(a[0] - b[0]), abs(a[1] - b[1])
    lo, hi = min(dr, dc), max(dr, dc)
    return (hi - lo) * 1.0 + lo * DIAG


def zero(_a: tuple[int, int], _b: tuple[int, int]) -> float:
    """Dijkstra 的启发式：h ≡ 0。"""
    return 0.0


def neighbors(grid: list[list[int]], node: tuple[int, int]):
    rows, cols = len(grid), len(grid[0])
    r, c = node
    for dr, dc in STRAIGHT:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0:
            yield (nr, nc), 1.0
    for dr, dc in DIAGONAL:
        nr, nc = r + dr, c + dc
        if not (0 <= nr < rows and 0 <= nc < cols):
            continue
        if grid[nr][nc] == 1:
            continue
        if grid[r + dr][c] == 1 or grid[r][c + dc] == 1:
            continue  # 不允许贴角穿越
        yield (nr, nc), DIAG


def search(grid, start, goal, heuristic):
    """返回 (路径, 代价, 扩展节点数)；无解返回 (None, inf, 扩展数)。"""
    order = itertools.count()
    g = {start: 0.0}
    came: dict[tuple[int, int], tuple[int, int]] = {}
    closed: set[tuple[int, int]] = set()
    expanded = 0
    heap = [(heuristic(start, goal), next(order), start)]
    while heap:
        _, _, node = heapq.heappop(heap)
        if node in closed:
            continue
        closed.add(node)
        expanded += 1
        if node == goal:
            path = [node]
            while node != start:
                node = came[node]
                path.append(node)
            return path[::-1], g[goal], expanded
        for nb, cost in neighbors(grid, node):
            ng = g[node] + cost
            if ng < g.get(nb, math.inf) - EPS:
                g[nb] = ng
                came[nb] = node
                heapq.heappush(heap, (ng + heuristic(nb, goal), next(order), nb))
    return None, math.inf, expanded


def random_grid(rows: int, cols: int, wall_p: float, rng: random.Random,
                start: tuple[int, int], goal: tuple[int, int]) -> list[list[int]]:
    while True:
        grid = [
            [1 if rng.random() < wall_p and (r, c) not in (start, goal) else 0
             for c in range(cols)]
            for r in range(rows)
        ]
        if reachable(grid, start, goal):
            return grid


def reachable(grid, start, goal) -> bool:
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            return True
        for nb, _cost in neighbors(grid, node):
            if nb not in seen:
                seen.add(nb)
                queue.append(nb)
    return False


def main() -> None:
    start, goal = (0, 0), (14, 14)
    print("八邻域 A* vs Dijkstra（15×15，25% 障碍，5 张固定种子地图）")
    header = f"{'seed':>4} | {'A* 代价':>8} | {'Dijkstra':>8}"
    print(f"{header} | {'A* 扩展':>7} | {'Dijkstra 扩展':>13}")
    print("-" * 60)
    worse = 0
    for seed in range(5):
        grid = random_grid(15, 15, 0.25, random.Random(seed), start, goal)
        a_path, a_cost, a_exp = search(grid, start, goal, octile)
        d_path, d_cost, d_exp = search(grid, start, goal, zero)
        assert a_path is not None and d_path is not None, f"seed={seed}: 应连通"
        assert abs(a_cost - d_cost) < EPS, f"seed={seed}: {a_cost} != {d_cost}"
        worse += a_exp >= d_exp
        print(f"{seed:>4} | {a_cost:>8.2f} | {d_cost:>8.2f} | {a_exp:>7} | {d_exp:>13}")
    print("-" * 60)
    print(f"五张地图代价全部一致；A* 扩展数不少于 Dijkstra 的地图数：{worse}/5")
    print("说明：八邻域下曼哈顿距离会高估（对角一步只省 1 而它是 √2），必须换 octile。")


if __name__ == "__main__":
    main()
