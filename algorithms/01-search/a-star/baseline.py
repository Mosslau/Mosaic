"""Dijkstra 对照实现（无启发式，等价于 h ≡ 0 的 A*）

作为 A* 的基线对照：两者返回同一结果类型 SearchResult，
demo 里对比"启发式到底省了多少扩展节点"。
"""

from impl import SearchResult, solve


def dijkstra(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> SearchResult:
    """Dijkstra 最短路径，接口与 A* 对齐（没有 heuristic 参数）。

    逻辑 = A* 去掉启发式：直接复用 solve，令 h ≡ 0。
    这个写法本身就是论点：Dijkstra = h≡0 的 A*。
    """
    return solve(grid, start, goal, heuristic=lambda a, b: 0)


if __name__ == "__main__":
    raise SystemExit("请先完成 dijkstra()，由 demo.py 统一调用对比")
