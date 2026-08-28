"""A* demo：同一张地图，手写 A* vs Dijkstra 双跑对比。

搜索算法的"对照"是基线算法而非 sklearn：
- 同一张随机障碍地图（固定随机种子，保证起点终点连通）
- 分别跑 impl.solve（A*）与 baseline.dijkstra（Dijkstra）
- 对比 路径长度 / 扩展节点数 / 耗时 —— 启发式 h 的收益由此量化
"""

import time

from impl import solve
from baseline import dijkstra


def make_grid(rows: int = 21, cols: int = 21, obstacle_ratio: float = 0.3, seed: int = 42):
    """TODO: 生成随机障碍地图（0=通路，1=障碍），保证 (1,1) 与 (rows-2, cols-2) 连通。"""
    raise NotImplementedError


def draw(grid, path_a: list, path_d: list) -> None:
    """TODO: matplotlib 画地图 + 两条路径，保存图片到本目录。"""
    raise NotImplementedError


def main() -> None:
    grid = make_grid()
    start, goal = (1, 1), (19, 19)

    t0 = time.perf_counter()
    r_a = solve(grid, start, goal)
    t_a = time.perf_counter() - t0

    t0 = time.perf_counter()
    r_d = dijkstra(grid, start, goal)
    t_d = time.perf_counter() - t0

    print(f"{'':14} | {'A*':>10} | {'Dijkstra':>10}")
    print("-" * 42)
    print(f"{'path_len':14} | {len(r_a.path) if r_a.path else 0:>10} | {len(r_d.path) if r_d.path else 0:>10}")
    print(f"{'nodes_expanded':14} | {r_a.nodes_expanded:>10} | {r_d.nodes_expanded:>10}")
    print(f"{'time_sec':14} | {t_a:>10.4f} | {t_d:>10.4f}")

    draw(grid, r_a.path, r_d.path)
    # 结论写回本目录 README.md 的「实验结果」一节


if __name__ == "__main__":
    main()
