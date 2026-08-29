"""无信息搜索三兄弟：DFS / BFS / UCS（Dijkstra）。

核心论点：它们是**同一个搜索循环**，区别只在 frontier 取节点的优先级：
    DFS      取最新（栈）
    BFS      取最早（队列）
    UCS      取累计代价 g 最小（优先队列）

本文件把这个论点直接写进代码：三者共享同一个 `_search`，
frontier 是一个鸭子类型——Stack / Queue / PriorityQueue。
"""

from collections import deque
from dataclasses import dataclass, field
import heapq
import itertools
from typing import Iterator, Optional

from grid_utils import Grid, Pos, neighbors, reconstruct


@dataclass
class SearchResult:
    """一次搜索的结果（六算法共用，便于并排对比）。"""

    path: Optional[list[Pos]]   # start → goal 的路径（含两端）；无解为 None
    nodes_expanded: int         # 从 frontier 取出的节点数（工作量指标）
    path_cost: float            # 路径总代价（无解为 inf）
    closed: set[Pos] = field(default_factory=set)  # 已扩展节点（可视化用）


# ---------- frontier 的三种形态 ----------

class _Stack:
    """DFS：后进先出。"""

    def __init__(self):
        self._items: list = []

    def push(self, priority: float, node: Pos) -> None:
        self._items.append(node)          # priority 被忽略

    def pop(self) -> Pos:
        return self._items.pop()

    def __len__(self) -> int:
        return len(self._items)


class _Queue:
    """BFS：先进先出。"""

    def __init__(self):
        self._items: deque = deque()

    def push(self, priority: float, node: Pos) -> None:
        self._items.append(node)          # priority 被忽略

    def pop(self) -> Pos:
        return self._items.popleft()

    def __len__(self) -> int:
        return len(self._items)


class _PriorityQueue:
    """UCS：g 最小优先（heapq 最小堆）。"""

    def __init__(self):
        self._heap: list = []
        self._counter = itertools.count()  # 平局破解：保证堆元素可比

    def push(self, priority: float, node: Pos) -> None:
        heapq.heappush(self._heap, (priority, next(self._counter), node))

    def pop(self) -> Pos:
        return heapq.heappop(self._heap)[2]

    def __len__(self) -> int:
        return len(self._heap)


# ---------- 统一搜索循环 ----------

def _search(grid: Grid, start: Pos, goal: Pos, frontier) -> SearchResult:
    """模板方法：取节点 → 判目标 → 扩展邻居 → 入 frontier。

    优先级由 frontier 的实现决定；g_score 记录最优已知代价，
    UCS 用它做松弛，DFS/BFS 退化为 visited 判重。
    """
    g_score: dict[Pos, float] = {start: 0.0}
    came_from: dict[Pos, Pos] = {}
    closed: set[Pos] = set()
    frontier.push(0.0, start)
    expanded = 0

    while frontier:
        node = frontier.pop()
        if node in closed:
            continue                      # 过期项（堆中可能残留旧 g 值）
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
            g2 = g_score[node] + 1        # 四方向网格每步代价 1
            if g2 < g_score.get(nb, float("inf")):
                g_score[nb] = g2
                came_from[nb] = node
                frontier.push(g2, nb)     # 栈/队列忽略 g2，堆用它排序

    return SearchResult(path=None, nodes_expanded=expanded,
                        path_cost=float("inf"), closed=closed)


# ---------- 三个公开接口 ----------

def dfs(grid: Grid, start: Pos, goal: Pos) -> SearchResult:
    """深度优先：一条道走到黑。不保证最短，内存最小。"""
    return _search(grid, start, goal, _Stack())


def bfs(grid: Grid, start: Pos, goal: Pos) -> SearchResult:
    """广度优先：水波扩散。无权图保证最短。"""
    return _search(grid, start, goal, _Queue())


def ucs(grid: Grid, start: Pos, goal: Pos) -> SearchResult:
    """一致代价搜索：g 最小优先。非负权保证最短。

    本实现边权恒为 1，因此 UCS ≡ BFS（结果完全一致，只是排序机制不同）。
    在 `a-star/baseline.py` 中它以 Dijkstra 的名字出现，与 A* 对照。
    """
    return _search(grid, start, goal, _PriorityQueue())


# 别名：算法上 Dijkstra ≡ UCS，只是工程语境的全源叫法
dijkstra = ucs


# ---------- 自测 ----------

if __name__ == "__main__":
    from grid_utils import make_grid, render

    grid, start, goal = make_grid(seed=42)
    print(f"地图 {len(grid)}x{len(grid[0])}，start={start}，goal={goal}\n")

    for name, fn in [("DFS", dfs), ("BFS", bfs), ("UCS", ucs)]:
        r = fn(grid, start, goal)
        plen = len(r.path) if r.path else "无解"
        print(f"{name:4} | 路径长度 {plen:>4} | 扩展节点 {r.nodes_expanded:>4} | 代价 {r.path_cost}")

    print("\nBFS 结果可视化（# 障碍  * 路径  o 扩展过）:")
    r = bfs(grid, start, goal)
    print(render(grid, r.path, r.closed))
