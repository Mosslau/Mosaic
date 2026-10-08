"""对照实现：两件事必须分开——**教学对照**与**独立参考**。

- `dijkstra`：教学对照，**不是独立参考**。它复用 impl.solve 并令 h ≡ 0，
  用一行代码证明"Dijkstra = h≡0 的 A*"。代价是它与被测实现共享全部堆逻辑：
  solve 的最优性若有缺陷，A* 与"基线"会一起错、且永远相等——所以它只能用来
  对比扩展节点数（效率），**不能用来验证最优性**。
- `bfs_shortest_cost`：独立参考。完全不复用 impl.py 的 BFS，用队列层数给出
  无权网格上的最短步数。test_impl.py 用它做差分验证，"最优性"才站得住。

手写纪律：两者都是手写（未调用 networkx 等现成图搜索库）。
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional

from impl import SearchResult, solve


def dijkstra(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> SearchResult:
    """Dijkstra 最短路径，接口与 A* 对齐（没有 heuristic 参数）。

    逻辑 = A* 去掉启发式：直接复用 solve，令 h ≡ 0。
    这个写法本身就是论点：Dijkstra = h≡0 的 A*。

    **注意：这不是独立参考实现**——它和被验证的 A* 是同一份 solve()。
    用途仅限"同图对照扩展节点数"；最优性验证请用 `bfs_shortest_cost`。
    """
    return solve(grid, start, goal, heuristic=lambda a, b: 0)


@dataclass
class ReferenceResult:
    """独立参考的返回：最短步数（不可达为 None）+ 出队节点数。"""

    path_cost: Optional[int]  # 无权网格上 = 最短步数；不可达为 None
    nodes_expanded: int       # 出队节点数，与 SearchResult 同口径可比


def _check_grid(grid: list[list[int]]) -> tuple[int, int]:
    """地图形状校验（独立参考自带一份，不 import impl 的私有函数）。"""
    if not grid:
        raise ValueError("grid 为空：至少要有一行（例如 [[0]]）")
    if any(len(row) == 0 for row in grid):
        raise ValueError("grid 有空行：每一行至少要有一列")
    widths = {len(row) for row in grid}
    if len(widths) > 1:
        raise ValueError(f"grid 不是矩形：各行长度不一致 {sorted(widths)}")
    return len(grid), len(grid[0])


def bfs_shortest_cost(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> ReferenceResult:
    """独立参考实现：无权网格 BFS，队列层数即最短步数。

    刻意不复用 impl.py 的任何代码——不共享堆、不共享平局策略、不共享松弛逻辑。
    四方向单步代价恒为 1，故"最少步数"就是最优路径代价，可与 A* 的 `path_cost`
    直接比较。这是本实验最优性断言的**外部**依据。

    参数与返回口径与 `solve` 对齐：0=可通行、1=障碍；起终点须在界内且可通行。
    """
    rows, cols = _check_grid(grid)
    for name, node in (("start", start), ("goal", goal)):
        r, c = node
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(f"{name}={node} 越界（地图 {rows}×{cols}）")
        if grid[r][c] != 0:
            raise ValueError(f"{name}={node} 落在障碍上")

    dist: dict[tuple[int, int], int] = {start: 0}
    queue: deque[tuple[int, int]] = deque([start])
    expanded = 0
    while queue:
        node = queue.popleft()
        expanded += 1
        if node == goal:
            return ReferenceResult(path_cost=dist[node], nodes_expanded=expanded)
        r, c = node
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if 0 <= nb[0] < rows and 0 <= nb[1] < cols and grid[nb[0]][nb[1]] == 0:
                if nb not in dist:
                    dist[nb] = dist[node] + 1
                    queue.append(nb)
    return ReferenceResult(path_cost=None, nodes_expanded=expanded)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一双跑对比：python3 demo.py")
