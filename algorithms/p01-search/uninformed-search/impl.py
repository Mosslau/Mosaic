"""DFS / BFS / UCS 三种无信息搜索 — 手写实现（搜索求解器）

三个算法解决**同一个问题**：在一张图上从起点走到终点。它们的区别只有一条：
**"下一个先看谁"**——而这个选择决定了三件事（是否最优、扩多少、占多少内存）。

- `dfs`：用**栈**，总是先看"刚放进来的"点 → 一条道走到黑
- `bfs`：用**队列**，总是先看"最早放进来的"点 → 像水波一圈圈向外
- `ucs`：用**优先队列（按累计代价）**，总是先看"当前最便宜"的点 → 像水波但按代价分层

本目录的形态由"图搜索"决定，没有 fit/predict：
- impl.py  三个算法的共同骨架 + 各自的"取点"策略
- demo.py  同一张地图上对比扩展顺序、扩展数、内存尖峰与路径质量
- project/ 用迭代加深 + IDA* 解 8 数码（把"要不要记忆"这条线走完）

记账口径（三者**必须一致**，否则数字无法比较）：
- `expanded`：从**边界**里取出并处理的节点数（= 出栈 / 出队 / 出堆次数）
- `peak_frontier`：搜索过程中**边界**的最大规模（栈 / 队列 / 堆的峰值）——内存的代理指标
- 边界里可能有重复节点（DFS/BFS 都允许重复入边界），靠"取出时判 visited"去重；
  这与教学 A* 实现的「closed 延迟删除」是同一套工程手法
"""

import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

Pos = tuple[int, int]
Grid = list[list[int]]

#: 四方向移动（上 / 下 / 左 / 右）
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


@dataclass
class SearchResult:
    """三个算法共用的返回类型，便于并排对比。"""

    path: Optional[list[Pos]]          # 从起点到终点的路径（含两端）；无解为 None
    cost: float                        # 路径总代价（无权图 = 步数）
    expanded: int                      # 从边界取出的节点数（工作量指标）
    peak_frontier: int                 # 边界峰值（内存代理指标）
    order: list[Pos] = field(default_factory=list)   # 取出顺序（只在小图上记录，供教学观察）


# ---------------------------------------------------------------- 地图与校验

def neighbors(grid: Grid, node: Pos) -> list[Pos]:
    """四方向可通行邻居（0 = 可走，其余 = 障碍 / 地形代价由 cost_of 负责）。"""
    rows, cols = len(grid), len(grid[0])
    r, c = node
    out = []
    for dr, dc in DIRECTIONS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] != -1:
            out.append((nr, nc))
    return out


def _check(grid: Grid, start: Pos, goal: Pos) -> tuple[int, int]:
    """入参校验（口径与 A* 实验一致：非法入参统一 ValueError）。"""
    if not grid:
        raise ValueError("grid 为空：至少要有一行")
    if any(len(row) == 0 for row in grid):
        raise ValueError("grid 有空行：每一行至少要有一列")
    widths = {len(row) for row in grid}
    if len(widths) > 1:
        raise ValueError(f"grid 不是矩形：各行长度不一致 {sorted(widths)}")
    rows, cols = len(grid), len(grid[0])
    for name, (r, c) in (("start", start), ("goal", goal)):
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(f"{name}={ (r, c) } 越界（地图 {rows}×{cols}）")
        if grid[r][c] == -1:
            raise ValueError(f"{name}={ (r, c) } 落在障碍上")
    return rows, cols


def _reconstruct(prev: dict, start: Pos, goal: Pos, cost: float,
                 expanded: int, peak: int, order: list) -> SearchResult:
    path, node = [], goal
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return SearchResult(path=path, cost=cost, expanded=expanded,
                        peak_frontier=peak, order=order)


# ---------------------------------------------------------------- 三个算法

def dfs(grid: Grid, start: Pos, goal: Pos, record_order: bool = False) -> SearchResult:
    """深度优先：用**栈**，总取最后放进去的节点。

    特点：一条道走到黑，**不保证最短**；内存小（只需存一条路径的边界）。
    注意：用"入栈时看不看 visited"有讲究——入栈时判重（本实现）可避免同一个点被压很多次，
    但会让栈里存在"到它更短的路径被挡住"的情况；**DFS 本来就不保证最优，所以无所谓**。
    """
    _check(grid, start, goal)
    prev: dict = {start: None}
    seen = {start}
    stack: list[Pos] = [start]
    expanded = peak = 0
    order: list[Pos] = []
    while stack:
        peak = max(peak, len(stack))
        node = stack.pop()
        expanded += 1
        if record_order:
            order.append(node)
        if node == goal:
            steps = 0
            n = goal
            while prev[n] is not None:
                steps += 1
                n = prev[n]
            return _reconstruct(prev, start, goal, float(steps), expanded, peak, order)
        for nb in neighbors(grid, node):
            if nb not in seen:
                seen.add(nb)
                prev[nb] = node
                stack.append(nb)
    return SearchResult(path=None, cost=float("inf"), expanded=expanded,
                        peak_frontier=peak, order=order)


def bfs(grid: Grid, start: Pos, goal: Pos, record_order: bool = False) -> SearchResult:
    """广度优先：用**队列**，总取最早放进去的节点。

    特点：无权图上**保证步数最少**；代价是内存——边界里存着整整一层，可能指数膨胀。
    """
    _check(grid, start, goal)
    prev: dict = {start: None}
    seen = {start}
    queue: deque[Pos] = deque([start])
    dist = {start: 0}
    expanded = peak = 0
    order: list[Pos] = []
    while queue:
        peak = max(peak, len(queue))
        node = queue.popleft()
        expanded += 1
        if record_order:
            order.append(node)
        if node == goal:
            return _reconstruct(prev, start, goal, float(dist[node]), expanded, peak, order)
        for nb in neighbors(grid, node):
            if nb not in seen:
                seen.add(nb)
                prev[nb] = node
                dist[nb] = dist[node] + 1
                queue.append(nb)
    return SearchResult(path=None, cost=float("inf"), expanded=expanded,
                        peak_frontier=peak, order=order)


def ucs(grid: Grid, start: Pos, goal: Pos, cost_of: Optional[Callable[[Pos], float]] = None,
        record_order: bool = False) -> SearchResult:
    """一致代价搜索：用**优先队列**，总取"累计代价最小"的节点。

    特点：**带权图上保证总代价最小**（BFS 只是它在"每步代价都是 1"时的特例）。
    与 A* 的唯一差别：它没有 h，所以只能按 g 排队——这就是"无信息"的含义。

    参数 `cost_of(node)`：进入 `node` 的代价（默认恒为 1）。调用方需保证非负。
    """
    _check(grid, start, goal)
    enter_cost = cost_of if cost_of is not None else (lambda _n: 1.0)
    prev: dict = {start: None}
    dist: dict = {start: 0.0}
    heap: list = [(0.0, start)]
    expanded = peak = 0
    order: list[Pos] = []
    while heap:
        peak = max(peak, len(heap))
        d, node = heapq.heappop(heap)
        if d > dist.get(node, float("inf")):
            continue                      # 过期堆项：与 A* 同款处理
        expanded += 1
        if record_order:
            order.append(node)
        if node == goal:
            return _reconstruct(prev, start, goal, d, expanded, peak, order)
        for nb in neighbors(grid, node):
            nd = d + enter_cost(nb)
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                prev[nb] = node
                heapq.heappush(heap, (nd, nb))
    return SearchResult(path=None, cost=float("inf"), expanded=expanded,
                        peak_frontier=peak, order=order)


#: 统一入口（demo 与测试都走这里，避免各处拼名字）
ALGORITHMS = {
    "dfs": dfs,
    "bfs": bfs,
    "ucs": ucs,
}


def describe() -> dict:
    """三个算法的"取点规则"，供 README / demo 直接引用（单一事实来源）。"""
    return {
        "dfs": "栈（LIFO）：总取最后放进去的 → 一条道走到黑",
        "bfs": "队列（FIFO）：总取最早放进来的 → 一圈圈向外",
        "ucs": "优先队列（按累计代价）：总取当前最便宜 → 按代价分层向外",
    }


if __name__ == "__main__":
    raise SystemExit("本文件是搜索库，跑实验请执行：python3 demo.py")
