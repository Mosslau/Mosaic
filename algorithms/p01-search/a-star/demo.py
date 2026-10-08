"""A* demo：同一张地图，手写 A*（insertion / large_g）vs Dijkstra 三跑对比 + 两个变参实验。

搜索算法的"对照"是基线算法而非 sklearn。三个实验：
1. 主对照：同一张随机障碍地图（固定种子，保证连通），A*（insertion / large_g
   两种平局策略）+ Dijkstra + h≡0+large_g 四跑对比，并单独跑一遍独立 BFS
   参考（不复用 impl.py）作为最优性的外部依据 ——
   启发式收益与平局策略收益由此分开归因
2. 平局策略 × 障碍率：无障碍 / 30% 障碍两张图，各跑 insertion 与 large_g
   两种平局破解（含独立 BFS 参考校验）—— 展示"平局策略是网格 A* 效率的一阶因素"
3. 加权 A* 扫描：w ∈ {1.0, 2.0, 3.0, 5.0}，f = g + w·h ——
   展示"牺牲最优性换扩展节点数"的对换曲线

本文件自带网格工具（make_grid / render），不依赖外部共享模块，保证实验可独立复现。
"""

import random
import time
from collections import deque

from impl import solve
from baseline import bfs_shortest_cost, dijkstra

Grid = list[list[int]]
Pos = tuple[int, int]

ROWS = COLS = 21
START, GOAL = (1, 1), (ROWS - 2, COLS - 2)
TIME_REPEATS = 20  # 耗时基准的重复次数（单次 <1ms，单跑值全是噪声）


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


def make_grid(rows: int = ROWS, cols: int = COLS, obstacle_ratio: float = 0.3,
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


def make_empty_grid(rows: int = ROWS, cols: int = COLS) -> Grid:
    """无障碍地图（仅边界墙）：曼哈顿启发式在此是紧的，f 值全场平局。"""
    grid = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        grid[i][0] = grid[i][cols - 1] = 1
    for j in range(cols):
        grid[0][j] = grid[rows - 1][j] = 1
    return grid


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


def bench_ms(fn, repeats: int = TIME_REPEATS) -> tuple[float, float, float]:
    """重复跑 fn 并返回 (中位数, 最小, 最大) 毫秒。

    为什么不用单次值：本实验规模下单次耗时 <1ms，同一张图重复跑波动可达 ~10%，
    且"谁更快"的排序每次都在变。扩展节点数是确定性的，耗时只作量级参考——
    所以取中位数并给出区间。
    """
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return samples[len(samples) // 2], samples[0], samples[-1]


def experiment_main() -> None:
    """实验一：A* vs Dijkstra 主对照（30% 障碍，seed=42；A* 含两种平局策略）。

    归因要求把两个变量分开：h 的有无（启发式收益）× 平局策略（边界集收益）。
    因此除 A*(insertion) / A*(large_g) / Dijkstra 外，还跑 h≡0 + large_g
    作为第四条基线——它与 Dijkstra 只差平局策略，与 A*(large_g) 只差 h。
    """
    print("== 实验一：A* vs Dijkstra（21×21，30% 障碍，seed=42）==")
    grid, start, goal = make_grid()

    r_ins = solve(grid, start, goal)                      # h=manhattan, insertion
    r_lg = solve(grid, start, goal, tie_break="large_g")  # h=manhattan, large_g
    r_d = dijkstra(grid, start, goal)                     # h≡0,        insertion
    r_h0_lg = solve(grid, start, goal, heuristic=lambda a, b: 0,
                    tie_break="large_g")                  # h≡0,        large_g
    ref = bfs_shortest_cost(grid, start, goal)            # 独立参考（不复用 impl.py）

    # 断言一：四条跑法必须找到相同代价的最短路径
    assert r_ins.path_cost == r_lg.path_cost == r_d.path_cost == r_h0_lg.path_cost, (
        f"最优性破坏：insertion {r_ins.path_cost}、large_g {r_lg.path_cost}、"
        f"Dijkstra {r_d.path_cost}、h≡0+large_g {r_h0_lg.path_cost}"
    )
    # 断言二：与独立 BFS 参考对齐——这才是最优性的外部依据
    assert ref.path_cost == r_ins.path_cost, (
        f"独立参考不一致：BFS {ref.path_cost} ≠ A* {r_ins.path_cost}"
    )

    len_ins = len(r_ins.path) if r_ins.path else 0
    len_lg = len(r_lg.path) if r_lg.path else 0
    len_d = len(r_d.path) if r_d.path else 0
    print(f"{'':18} | {'A*(ins)':>8} | {'A*(lg)':>7} | {'Dijkstra':>8} | {'h=0+lg':>7}")
    print("-" * 62)
    print(f"{'path_len(节点数)':18} | {len_ins:>8} | {len_lg:>7} | {len_d:>8} | {'—':>7}")
    print(f"{'path_cost(代价)':18} | {r_ins.path_cost:>8.0f} | {r_lg.path_cost:>7.0f} | "
          f"{r_d.path_cost:>8.0f} | {r_h0_lg.path_cost:>7.0f}")
    print(f"{'nodes_expanded':18} | {r_ins.nodes_expanded:>8} | {r_lg.nodes_expanded:>7} | "
          f"{r_d.nodes_expanded:>8} | {r_h0_lg.nodes_expanded:>7}")
    print(f"（独立 BFS 参考：最短步数 {ref.path_cost}，出队 {ref.nodes_expanded} 个节点）")

    print()
    print("归因（扩展节点数，逐变量对比）：")
    h_gain_ins = r_d.nodes_expanded - r_ins.nodes_expanded
    print(f"  启发式收益（insertion 平局）：{r_d.nodes_expanded} → {r_ins.nodes_expanded}"
          f"，少 {h_gain_ins} 个（{h_gain_ins / r_d.nodes_expanded:.1%}）")
    h_gain_lg = r_h0_lg.nodes_expanded - r_lg.nodes_expanded
    print(f"  启发式收益（large_g 平局）：  {r_h0_lg.nodes_expanded} → {r_lg.nodes_expanded}"
          f"，少 {h_gain_lg} 个（{h_gain_lg / r_h0_lg.nodes_expanded:.1%}）")
    tie_gain_h0 = r_d.nodes_expanded - r_h0_lg.nodes_expanded
    print(f"  平局策略收益（h≡0）：        {r_d.nodes_expanded} → {r_h0_lg.nodes_expanded}"
          f"，少 {tie_gain_h0} 个（{tie_gain_h0 / r_d.nodes_expanded:.1%}）")
    tie_gain_h = r_ins.nodes_expanded - r_lg.nodes_expanded
    print(f"  平局策略收益（h=manhattan）：{r_ins.nodes_expanded} → {r_lg.nodes_expanded}"
          f"，少 {tie_gain_h} 个（{tie_gain_h / r_ins.nodes_expanded:.1%}）")

    print(f"\n耗时基准（{TIME_REPEATS} 次的中位数 [最小–最大]，单次 <1ms 只作量级参考）：")
    for name, fn in (("A*(insertion)", lambda: solve(grid, start, goal)),
                     ("A*(large_g)", lambda: solve(grid, start, goal, tie_break="large_g")),
                     ("Dijkstra", lambda: dijkstra(grid, start, goal))):
        med, lo, hi = bench_ms(fn)
        print(f"  {name:<14} {med:>6.3f} ms  [{lo:.3f}–{hi:.3f}]")

    draw(grid, r_ins.path, r_d.path, r_ins.closed, r_d.closed)


def experiment_tiebreak() -> None:
    """实验二：平局策略 × 障碍率（2×2）。

    无障碍地图上曼哈顿 h 是紧的 ⇒ 所有自由节点 f ≡ C*，扩展多少个
    f = C* 的节点完全由平局破解决定：insertion 退化为全图扩展，
    large_g 直冲终点（扩展数 = 路径节点数，理论下界）。
    """
    print("\n== 实验二：平局破解策略 × 障碍率 ==")
    cases = []
    for name, grid in (("无障碍", make_empty_grid()), ("30% 障碍", make_grid()[0])):
        optimal = dijkstra(grid, START, GOAL).path_cost  # Dijkstra 给出最优代价基准
        ref = bfs_shortest_cost(grid, START, GOAL).path_cost  # 独立参考（外部依据）
        cases.append((name, grid, optimal, ref))

    print(f"{'地图':<12} | {'insertion':>10} | {'large_g':>10} | {'最优代价':>8} | {'BFS参考':>7}")
    print("-" * 62)
    for name, grid, optimal, ref in cases:
        r_ins = solve(grid, START, GOAL)
        r_lg = solve(grid, START, GOAL, tie_break="large_g")
        # 两种平局策略都必须保持最优（平局只影响效率，不影响最优性），
        # 且与独立 BFS 参考一致（外部校验，不依赖 Dijkstra 基线）
        assert r_ins.path_cost == r_lg.path_cost == optimal == ref
        print(f"{name:<12} | {r_ins.nodes_expanded:>10} | {r_lg.nodes_expanded:>10} | "
              f"{optimal:>8.0f} | {ref:>7.0f}")
    print("观察：无障碍时所有节点 f 值相同，insertion 全图扩展而 large_g 直达下界；")
    print("      障碍使 g 绕路、f 值分层，平局策略的独立收益随之降为 0。")


def experiment_weight() -> None:
    """实验三：加权 A* 扫描，f = g + w·h（30% 障碍图，large_g 平局）。

    w = 1 最优；w > 1 不再保证最优，只保证 w-次优界——
    用扩展节点数换路径代价的对换由此量化。
    """
    print("\n== 实验三：加权 A*（f = g + w·h）==")
    grid, start, goal = make_grid()
    optimal = dijkstra(grid, start, goal).path_cost

    print(f"{'w':>5} | {'nodes_expanded':>14} | {'path_cost':>9} | {'相对最优':>8}")
    print("-" * 48)
    for w in (1.0, 2.0, 3.0, 5.0):
        r = solve(grid, start, goal, tie_break="large_g", weight=w)
        gap = (r.path_cost - optimal) / optimal
        print(f"{w:>5.1f} | {r.nodes_expanded:>14} | {r.path_cost:>9.0f} | {gap:>+8.1%}")
    print(f"观察：w ≤ 2 仍命中最优代价 {optimal:.0f}；w = 3 起代价变差——")
    print("      高估 h 让搜索更早冲向终点，但不再保证最优（最优性断言仅限 w = 1）。")


def main() -> None:
    experiment_main()
    experiment_tiebreak()
    experiment_weight()
    # 结论写回本目录 README.md 的「实验结果」一节


if __name__ == "__main__":
    main()
