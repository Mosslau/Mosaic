"""网格地图公共工具：生成、验证、邻居、显示。

六个搜索算法共用同一种问题形态——四方向网格寻路：
    grid[r][c] == 0  可通行
    grid[r][c] == 1  障碍
"""

from collections import deque
import random

Grid = list[list[int]]
Pos = tuple[int, int]


def make_grid(rows: int = 21, cols: int = 21, obstacle_ratio: float = 0.3,
              seed: int = 42) -> tuple[Grid, Pos, Pos]:
    """生成随机障碍地图，保证 start=(1,1) 与 goal=(rows-2, cols-2) 连通。

    做法：随机撒障碍 → BFS 洪泛检查连通 → 不连通则重试。
    """
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


def neighbors(grid: Grid, node: Pos) -> list[Pos]:
    """四方向可通行邻居（上下左右，代价均为 1）。"""
    r, c = node
    out = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]) and grid[nr][nc] == 0:
            out.append((nr, nc))
    return out


def reconstruct(came_from: dict[Pos, Pos], goal: Pos) -> list[Pos]:
    """由父指针链回溯完整路径（含 start 与 goal）。"""
    path = [goal]
    while path[-1] in came_from:
        path.append(came_from[path[-1]])
    path.reverse()
    return path


def render(grid: Grid, path: list[Pos] | None = None,
           closed: set[Pos] | None = None) -> str:
    """ASCII 渲染：# 障碍  . 通路  * 路径  o 扩展过  S/G 起终点。"""
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
