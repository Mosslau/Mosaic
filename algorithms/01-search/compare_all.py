"""六算法同台对比：DFS / BFS / UCS / 贪心 / A*，外加 a-star 目录的 Dijkstra。

同一张随机障碍地图（固定种子，保证连通），全部跑一遍，
并排对比 路径长度 / 扩展节点数 / 耗时 / 是否最优。

用法：
    python compare_all.py              # 默认 21x21、30% 障碍
    python compare_all.py 31 0.35 7    # 自定义 rows、障碍率、种子
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))            # grid_utils / uninformed / heuristic
sys.path.insert(0, str(Path(__file__).parent / "a-star")) # impl / baseline

from grid_utils import make_grid, render
from uninformed import dfs, bfs, ucs
from heuristic import greedy, astar
from baseline import dijkstra  # a-star/baseline.py：h≡0 的 A*


def run(name: str, fn, grid, start, goal):
    t0 = time.perf_counter()
    r = fn(grid, start, goal)
    dt = time.perf_counter() - t0
    return name, r, dt


def main() -> None:
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 21
    ratio = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42

    grid, start, goal = make_grid(rows, rows, ratio, seed)
    print(f"地图 {rows}x{rows}，障碍率 {ratio:.0%}，种子 {seed}")
    print(f"start={start}  goal={goal}\n")

    runs = [
        ("DFS", dfs),
        ("BFS", bfs),
        ("UCS", ucs),
        ("Dijkstra", dijkstra),
        ("贪心", greedy),
        ("A*", astar),
    ]

    results = [run(name, fn, grid, start, goal) for name, fn in runs]
    optimal_cost = min(r.path_cost for _, r, _ in results)

    header = f"{'算法':<10} | {'路径长':>6} | {'扩展节点':>8} | {'耗时ms':>8} | 最优?"
    print(header)
    print("-" * len(header.encode("gbk")))  # 中文宽度对齐
    for name, r, dt in results:
        plen = len(r.path) if r.path else 0
        optimal = "✓" if r.path_cost == optimal_cost else "✗"
        print(f"{name:<10} | {plen:>6} | {r.nodes_expanded:>8} | {dt*1000:>8.3f} | {optimal}")

    # UCS / Dijkstra / A* 最优性断言：三者必须同代价
    costs = {r.path_cost for n, r, _ in results if n in ("UCS", "Dijkstra", "A*")}
    assert len(costs) == 1, f"最优性破坏：{costs}"
    print(f"\n✓ UCS = Dijkstra = A* 代价一致（{optimal_cost}），最优性验证通过")

    # 启发式收益
    djk = next(r for n, r, _ in results if n == "Dijkstra")
    ast = next(r for n, r, _ in results if n == "A*")
    saved = djk.nodes_expanded - ast.nodes_expanded
    print(f"✓ A* 比 Dijkstra 少扩展 {saved} 个节点（{saved/djk.nodes_expanded:.1%}）")

    print("\nA* 结果（# 障碍  * 路径  o 扩展过）:")
    print(render(grid, ast.path, ast.closed))


if __name__ == "__main__":
    main()
