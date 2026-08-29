"""A* demo：同一张地图，手写 A* vs Dijkstra 双跑对比。

搜索算法的"对照"是基线算法而非 sklearn：
- 同一张随机障碍地图（固定随机种子，保证起点终点连通）
- 分别跑 impl.solve（A*）与 baseline.dijkstra（Dijkstra）
- 对比 路径长度 / 扩展节点数 / 耗时 —— 启发式 h 的收益由此量化
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # 让 grid_utils 可被导入

from grid_utils import make_grid as _make_grid, render
from impl import solve
from baseline import dijkstra


def make_grid(rows: int = 21, cols: int = 21, obstacle_ratio: float = 0.3, seed: int = 42):
    """生成随机障碍地图（0=通路，1=障碍），保证 (1,1) 与 (rows-2, cols-2) 连通。"""
    grid, start, goal = _make_grid(rows, cols, obstacle_ratio, seed)
    return grid, start, goal


def draw(grid, path_a: list, path_d: list, closed_a: set, closed_d: set) -> None:
    """ASCII 渲染地图 + 两条路径 + 扩展区域。"""
    print("\nA*（* 路径  o 扩展过）:")
    print(render(grid, path_a, closed_a))
    print("\nDijkstra（* 路径  o 扩展过）:")
    print(render(grid, path_d, closed_d))


def main() -> None:
    grid, start, goal = make_grid()

    t0 = time.perf_counter()
    r_a = solve(grid, start, goal)
    t_a = time.perf_counter() - t0

    t0 = time.perf_counter()
    r_d = dijkstra(grid, start, goal)
    t_d = time.perf_counter() - t0

    # 断言：同一张图，两算法必须找到相同代价的最短路径
    assert r_a.path_cost == r_d.path_cost, (
        f"最优性破坏：A* 代价 {r_a.path_cost} ≠ Dijkstra 代价 {r_d.path_cost}"
    )

    print(f"{'':16} | {'A*':>10} | {'Dijkstra':>10}")
    print("-" * 44)
    print(f"{'path_len':16} | {len(r_a.path) if r_a.path else 0:>10} | {len(r_d.path) if r_d.path else 0:>10}")
    print(f"{'nodes_expanded':16} | {r_a.nodes_expanded:>10} | {r_d.nodes_expanded:>10}")
    print(f"{'time_ms':16} | {t_a*1000:>10.3f} | {t_d*1000:>10.3f}")

    saved = r_d.nodes_expanded - r_a.nodes_expanded
    print(f"\n启发式收益：少扩展 {saved} 个节点（{saved/r_d.nodes_expanded:.1%}）")

    draw(grid, r_a.path, r_d.path, r_a.closed, r_d.closed)
    # 结论写回本目录 README.md 的「实验结果」一节


if __name__ == "__main__":
    main()
