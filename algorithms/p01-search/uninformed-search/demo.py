"""DFS / BFS / UCS demo：同一张地图上对比三个无信息搜索。

四组实验：
1. **小图看顺序**：5×5 小图上把三者的"取出顺序"打印出来——先搞懂它们只是在换"先看谁"
2. **同图比数字**：21×21 随机地图上比 路径代价 / 扩展数 / 内存尖峰
3. **带权地图**：BFS 的致命伤——它保证"步数最少"，但不保证"代价最小"
4. **邻接顺序的影响**：DFS 的结果随"先看哪个方向"而变（同一个算法给出不同答案）

另有一节把 **UCS 与 A***（星号）放在同一张无权地图上对照（引出"为什么需要 h"）。

口径（三个算法完全一致，否则数字不可比）：
- `expanded`：从边界取出的节点数
- `peak_frontier`：边界规模的最大值（栈 / 队列 / 堆峰值，内存的代理指标）
- 起点即终点、无解、越界等边界一并处理

运行：cd algorithms/p01-search/uninformed-search && python3 demo.py
依赖：只用标准库
"""

import random
import time
from collections import deque
from pathlib import Path
from typing import Callable, Optional

from baseline import astar_reference, to_astar_grid
from impl import Grid, Pos, SearchResult, bfs, dfs, describe, neighbors, ucs

ROWS = COLS = 21
OBSTACLE_RATIO = 0.3

# 带权地形的代价范围（进入一格的代价）
TERRAIN_MIN, TERRAIN_MAX = 1, 9


# ---------------------------------------------------------------- 造图

def make_grid(rows: int = ROWS, cols: int = COLS, obstacle_ratio: float = OBSTACLE_RATIO,
              seed: int = 42) -> tuple[Grid, Pos, Pos]:
    """随机障碍地图，起终点强制连通（拒绝采样 + 洪泛检查）。

    与 A* 实验同款造图：只有"保证连通"才能把对照聚焦在搜索策略上，而不是"这张图有没有解"。
    """
    rng = random.Random(seed)
    start, goal = (1, 1), (rows - 2, cols - 2)
    while True:
        grid = [[-1 if rng.random() < obstacle_ratio else 0 for _ in range(cols)]
                for _ in range(rows)]
        grid[start[0]][start[1]] = 0
        grid[goal[0]][goal[1]] = 0
        if _reachable(grid, start, goal):
            return grid, start, goal


def _reachable(grid: Grid, start: Pos, goal: Pos) -> bool:
    seen, q = {start}, deque([start])
    while q:
        node = q.popleft()
        if node == goal:
            return True
        for nb in neighbors(grid, node):
            if nb not in seen:
                seen.add(nb)
                q.append(nb)
    return False


def make_terrain(rows: int = ROWS, cols: int = COLS, obstacle_ratio: float = 0.2,
                 seed: int = 7) -> tuple[Grid, Pos, Pos]:
    """带权地形图：每格是 1–9 的进入代价（-1 表示不可通行）。

    为什么需要它：在"每步代价都是 1"的图上，BFS 与 UCS 完全等价，
    看不出区别；只有代价不均等时，才能暴露 BFS"步数最少 ≠ 代价最小"。
    """
    rng = random.Random(seed)
    start, goal = (1, 1), (rows - 2, cols - 2)
    while True:
        grid = []
        for _ in range(rows):
            row = []
            for _ in range(cols):
                row.append(-1 if rng.random() < obstacle_ratio
                           else rng.randint(TERRAIN_MIN, TERRAIN_MAX))
            grid.append(row)
        grid[start[0]][start[1]] = TERRAIN_MIN
        grid[goal[0]][goal[1]] = TERRAIN_MIN
        if _reachable(grid, start, goal):
            return grid, start, goal


def terrain_cost(node: Pos, grid: Grid) -> float:
    """UCS/A* 在带权图上的单步代价：进入该格的代价。"""
    return float(grid[node[0]][node[1]])


# ---------------------------------------------------------------- 实验一：小图看顺序

def experiment_order(rows: int = 5, cols: int = 5, seed: int = 3) -> dict:
    """小图上打印三个算法的**取出顺序**——它们做的事一样，只是"先看谁"不同。"""
    grid, start, goal = make_grid(rows, cols, obstacle_ratio=0.2, seed=seed)
    print(f"== 实验一：{rows}×{cols} 小图上的取出顺序（S={start} G={goal}，#=障碍） ==")
    print("地图：")
    for r in range(rows):
        print("   " + "".join("#" if grid[r][c] == -1 else "." for c in range(cols)))
    print()
    print("取点规则（三个算法的唯一区别）：")
    for name, rule in describe().items():
        print(f"   {name}：{rule}")
    print()

    results = {}
    for name, fn in (("dfs", dfs), ("bfs", bfs), ("ucs", ucs)):
        r = fn(grid, start, goal, record_order=True)
        results[name] = r
        seq = " → ".join(f"({a},{b})" for a, b in r.order[:12])
        more = " …" if len(r.order) > 12 else ""
        print(f"   {name}：取出 {r.expanded} 个，顺序：{seq}{more}")
        print(f"        步数 {len(r.path) - 1}（无权图，步数即代价），"
              f"路径：{' → '.join(f'({a},{b})' for a, b in r.path)}")
    print()
    assert len(results["bfs"].path) <= len(results["dfs"].path), "BFS 的步数不该比 DFS 多"
    return results


# ---------------------------------------------------------------- 实验二：同图比数字

def experiment_compare(games: int = 5, rows: int = ROWS, cols: int = COLS) -> list:
    """无权随机图上跑多张地图，比代价 / 扩展数 / 内存尖峰。"""
    print(f"\n== 实验二：{rows}×{cols} 无权地图 × {games} 张（30% 障碍） ==")
    print(f"{'地图':>4} | {'算法':>4} | {'步数':>5} | {'代价':>5} | {'扩展':>6} | {'内存尖峰':>8} | {'耗时(ms)':>8}")
    print("-" * 62)
    rows_out = []
    for i in range(games):
        grid, start, goal = make_grid(rows, cols, seed=42 + i)
        for name, fn in (("dfs", dfs), ("bfs", bfs), ("ucs", ucs)):
            t0 = time.perf_counter()
            r = fn(grid, start, goal)
            ms = (time.perf_counter() - t0) * 1000
            rows_out.append((i, name, r, ms))
            print(f"{i:>4} | {name:>4} | {len(r.path) - 1:>5} | {r.cost:>5.0f} | "
                  f"{r.expanded:>6} | {r.peak_frontier:>8} | {ms:>8.2f}")
    print()
    print("读法：")
    print("  · BFS 的步数处处与 UCS 相同（无权图上两者等价），但**内存尖峰高得多**")
    print("  · DFS 扩展数常常最少，代价却可能更长——少干活 ≠ 干对活")
    return rows_out


def summarize_unweighted(rows_out: list) -> dict:
    """按算法汇总（均值），并做两条断言：BFS 最优、UCS 与 BFS 同代价。"""
    agg: dict = {}
    for _, name, r, ms in rows_out:
        a = agg.setdefault(name, {"expanded": [], "peak": [], "cost": [], "ms": []})
        a["expanded"].append(r.expanded)
        a["peak"].append(r.peak_frontier)
        a["cost"].append(r.cost)
        a["ms"].append(ms)
    print(f"\n{'算法':>4} | {'平均扩展':>8} | {'平均内存尖峰':>12} | {'平均代价':>8} | {'平均耗时(ms)':>12}")
    print("-" * 62)
    for name, a in agg.items():
        n = len(a["cost"])
        print(f"{name:>4} | {sum(a['expanded']) / n:>8.0f} | {sum(a['peak']) / n:>12.0f} | "
              f"{sum(a['cost']) / n:>8.1f} | {sum(a['ms']) / n:>12.2f}")
    assert abs(sum(agg["bfs"]["cost"]) - sum(agg["ucs"]["cost"])) < 1e-9, \
        "无权图上 BFS 与 UCS 的代价必须完全一致"
    assert sum(agg["dfs"]["cost"]) >= sum(agg["bfs"]["cost"]), \
        "DFS 的总代价不该低于最优（否则说明地图或实现有问题）"
    return agg


# ---------------------------------------------------------------- 实验三：带权地图上 BFS 的致命伤

def experiment_weighted(games: int = 5, rows: int = ROWS, cols: int = COLS) -> list:
    """带权地形：BFS 按"步数"最优，UCS 按"代价"最优——两者会给出不同的路。"""
    print(f"\n== 实验三：带权地形（进入代价 1–9）× {games} 张 ==")
    print(f"{'地图':>4} | {'算法':>4} | {'步数':>5} | {'总代价':>7} | {'扩展':>6} | {'相对最优':>9}")
    print("-" * 56)
    rows_out = []
    for i in range(games):
        grid, start, goal = make_terrain(rows, cols, seed=200 + i)
        cost_of = lambda n, g=grid: terrain_cost(n, g)
        r_bfs = bfs(grid, start, goal)
        r_ucs = ucs(grid, start, goal, cost_of=cost_of)
        # BFS 找到的路径在"代价"口径下的真实总代价（它自己只保证步数）
        bfs_cost = float(sum(cost_of(n) for n in r_bfs.path[1:]))
        best = r_ucs.cost
        rows_out.append((i, r_bfs, bfs_cost, r_ucs))
        for name, r, cost in (("bfs", r_bfs, bfs_cost), ("ucs", r_ucs, r_ucs.cost)):
            gap = cost / best - 1 if best else 0.0
            print(f"{i:>4} | {name:>4} | {len(r.path) - 1:>5} | {cost:>7.0f} | "
                  f"{r.expanded:>6} | {gap:>8.1%}")
    worst = max(b[2] / b[3].cost - 1 for b in rows_out)
    print(f"\n→ BFS 的路径用「代价」衡量最差会**贵 {worst:.0%}**：它保证的是步数，不是代价")
    assert any(b[2] > b[3].cost for b in rows_out), (
        "带权图上 BFS 应当至少在一张图上次优——否则说明地形代价没生效")
    return rows_out


# ---------------------------------------------------------------- 实验四：邻接顺序影响 DFS

def experiment_dfs_order(seed: int = 42) -> dict:
    """DFS 的结果依赖"先看哪个方向"：同一张图、同一个算法，换个方向顺序换个答案。"""
    grid, start, goal = make_grid(seed=seed)
    import impl

    original = impl.DIRECTIONS
    try:
        variants = {
            "默认（上/下/左/右）": ((-1, 0), (1, 0), (0, -1), (0, 1)),
            "反向（右/左/下/上）": ((0, 1), (0, -1), (1, 0), (-1, 0)),
            "先横后纵（左/右/上/下）": ((0, -1), (0, 1), (-1, 0), (1, 0)),
        }
        out = {}
        print("\n== 实验四：DFS 的结果依赖邻接顺序（同一张 21×21 图） ==")
        print(f"{'邻接顺序':>22} | {'步数':>5} | {'扩展':>6} | {'内存尖峰':>8}")
        print("-" * 52)
        for label, dirs in variants.items():
            impl.DIRECTIONS = dirs
            r = dfs(grid, start, goal)
            out[label] = r
            print(f"{label:>22} | {len(r.path):>5} | {r.expanded:>6} | {r.peak_frontier:>8}")
        costs = {len(r.path) for r in out.values()}
        print(f"\n→ 同一个算法、同一张图，只是「先看哪个方向」不同，步数就出现 {sorted(costs)} 等多种结果")
        assert len(costs) > 1, "三种邻接顺序应当给出不同长度的路径——否则这个实验没有说服力"
        return out
    finally:
        impl.DIRECTIONS = original


# ---------------------------------------------------------------- 收尾：UCS vs A*

def experiment_ucs_vs_astar(seed: int = 42) -> dict:
    """UCS 与 A* 的**唯一差别**：A* 多了一个 h——走 `baseline.astar_reference`。

    为什么放在**无权**图上比：本目录的 UCS 与 A* 实验的 `solve` 都以"每步代价 = 1"为前提，
    只有在这个口径下两者的最优解才可比（带权口径的对照放在 README，各自引用各自实验的数字）。
    """
    grid, start, goal = make_grid(seed=seed)
    r_ucs = ucs(grid, start, goal)
    astar_grid = to_astar_grid(grid)
    r_ins = astar_reference(astar_grid, start, goal, tie_break="insertion")
    r_lg = astar_reference(astar_grid, start, goal, tie_break="large_g")

    print("\n== 收尾：UCS vs A*（同一张 21×21 无权地图，最优性口径相同） ==")
    print(f"{'算法':>14} | {'扩展':>6} | {'代价':>5}")
    print("-" * 32)
    print(f"{'UCS（无 h）':>14} | {r_ucs.expanded:>6} | {r_ucs.cost:>5.0f}")
    print(f"{'A*(insertion)':>14} | {r_ins.expanded:>6} | {r_ins.cost:>5.0f}")
    print(f"{'A*(large_g)':>14} | {r_lg.expanded:>6} | {r_lg.cost:>5.0f}")

    assert r_ucs.cost == r_ins.cost == r_lg.cost, \
        f"三者代价必须一致：{r_ucs.cost} / {r_ins.cost} / {r_lg.cost}"
    saved = 1 - r_lg.expanded / r_ucs.expanded
    print(f"\n→ 同样最优，A*(large_g) 比 UCS 少扩展 {r_ucs.expanded - r_lg.expanded} 个节点"
          f"（{saved:.1%}）——这就是 h 的全部作用：**把搜索从全向铺开拉成朝目标收缩**")
    return {"ucs": r_ucs, "astar_insertion": r_ins, "astar_large_g": r_lg, "saved": saved}


def main() -> None:
    experiment_order()
    rows_out = experiment_compare()
    summarize_unweighted(rows_out)
    experiment_weighted()
    experiment_dfs_order()
    experiment_ucs_vs_astar()


if __name__ == "__main__":
    main()
