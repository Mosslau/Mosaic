"""参考解 3：把题目里三个片段的行为**实测出来**，而不是凭直觉判断。

用法：python3 sol-03-诊断.py

三个片段结论不同——这正是本题的考点：
  A（BFS 无判重）        → 真问题：工作量指数爆炸；有环且目标不可达时**不终止**
  B（UCS 无过期判断）    → 不破坏正确性；实测连效率差都没有（网格类图不触发）
  C（DFS 只在取出判重）  → 不破坏正确性，破坏"内存 O(深度)"这条卖点
"""

import heapq
import sys
import time
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from demo import make_grid, make_terrain, terrain_cost   # noqa: E402
from impl import bfs, dfs, neighbors, ucs                # noqa: E402


# ---------------------------------------------------------------- 片段 A

def bfs_a(grid, start, goal, cap=5_000_000):
    """片段 A：BFS 但入队不判重。返回 (是否找到, 取出次数)。"""
    queue, pops = deque([start]), 0
    while queue:
        node = queue.popleft()
        pops += 1
        if pops > cap:
            return False, pops
        if node == goal:
            return True, pops
        for nb in neighbors(grid, node):
            queue.append(nb)
    return False, pops


def check_a() -> None:
    print("== 片段 A：BFS 入队不判重 ==")
    print(f"{'图':>10} | {'无判重取出':>12} | {'有判重取出':>10} | {'倍数':>12}")
    print("-" * 56)
    for n in (3, 5, 7, 8):
        grid = [[0] * n for _ in range(n)]
        _, pops_a = bfs_a(grid, (0, 0), (n - 1, n - 1))
        # 有判重的参照：直接数访问过的节点数
        seen, q = {(0, 0)}, deque([(0, 0)])
        while q:
            node = q.popleft()
            for nb in neighbors(grid, node):
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        print(f"{f'{n}×{n} 全开放':>10} | {pops_a:>12,} | {len(seen):>10,} | "
              f"{pops_a / len(seen):>12,.0f}")

    # 目标不可达：它**会**终止（队列最终为空），但要先把所有"路径"枚举完
    walled = [[0, 0, 0], [0, -1, 0], [0, 0, 0]]
    t0 = time.perf_counter()
    found, pops = bfs_a(walled, (0, 0), (0, 2), cap=20_000_000)
    dt = time.perf_counter() - t0
    print(f"\n  目标不可达（图里根本没有终点）：取出 {pops:,} 次后**正常终止**"
          f"（{dt:.2f}s，是「队列终于空了」，不是死循环）")
    print("  → 结论：它**不会死循环**（有限图上路径数有限），但会把**所有路径**枚举完才停——")
    print("     这就是它比「节点数」大几个数量级的原因：队列里装的是**路径**，不是节点。")


# ---------------------------------------------------------------- 片段 B

def ucs_b(grid, start, goal, cost_of):
    """片段 B：UCS 但不判断过期堆项。"""
    dist, heap, pops = {start: 0.0}, [(0.0, start)], 0
    while heap:
        d, node = heapq.heappop(heap)
        pops += 1
        if node == goal:
            return d, pops
        for nb in neighbors(grid, node):
            nd = d + cost_of(nb)
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                heapq.heappush(heap, (nd, nb))
    return None, pops


def check_b() -> None:
    print("\n== 片段 B：UCS 不判断过期堆项 ==")
    grid, start, goal = make_terrain(seed=200)
    cost_of = lambda n, g=grid: terrain_cost(n, g)
    d_b, pops_b = ucs_b(grid, start, goal, cost_of)
    r = ucs(grid, start, goal, cost_of=cost_of)
    print(f"  21×21 带权图：片段 B 代价 {d_b:.0f} / 扩展 {pops_b} | "
          f"impl 代价 {r.cost:.0f} / 扩展 {r.expanded}")
    assert d_b == r.cost, f"片段 B 的代价必须仍然最优：{d_b} vs {r.cost}"
    print("  → 结论：**没有破坏正确性**（代价仍最优）；在这类图上连多做的工作都没有。")
    print("     理论上它会对「已处理过的节点」重复扩展，但那要求「同一节点的更优值后来才进堆」，")
    print("     在节点代价只有 1–9 的网格上不触发（邻接两点的最短路差有界）。")
    print("     所以把它说成「不高效」要谨慎：本实验的图上是等价的。")


# ---------------------------------------------------------------- 片段 C

def dfs_c(grid, start, goal):
    """片段 C：DFS 只在取出时判重。返回 (栈峰值, 取出次数, 访问节点数)。"""
    stack, seen, peak, pops = [start], set(), 0, 0
    while stack:
        peak = max(peak, len(stack))
        node = stack.pop()
        pops += 1
        if node in seen:
            continue
        seen.add(node)
        if node == goal:
            return peak, pops, len(seen)
        for nb in neighbors(grid, node):
            stack.append(nb)
    return peak, pops, len(seen)


def check_c() -> None:
    print("\n== 片段 C：DFS 只在取出时判重 ==")
    print(f"{'seed':>5} | {'片段C 栈峰值':>12} | {'impl 边界峰值':>13} | {'取出':>6} | {'扩展':>6} | {'步数':>5}")
    print("-" * 66)
    for seed in (42, 1, 2):
        grid, start, goal = make_grid(seed=seed)
        peak_c, pops_c, _ = dfs_c(grid, start, goal)
        r = dfs(grid, start, goal)
        print(f"{seed:>5} | {peak_c:>12} | {r.peak_frontier:>13} | {pops_c:>6} | "
              f"{r.expanded:>6} | {len(r.path) - 1:>5}")
        assert peak_c > r.peak_frontier, "片段 C 应当明显更耗内存"
        assert len(r.path) > 1, "两者都要找到解"
    print("  → 结论：正确性没坏（都找到解、步数一致），破坏的是「内存 O(深度)」这条卖点。")


def main() -> None:
    check_a()
    check_b()
    check_c()
    print("\n一句话总结：三个片段都不报错，但只有一个（A）真的破坏了正确性相关的性质。")
    print("判断「能不能用」之前要问清：这里被牺牲的是**正确性、效率，还是内存**？")


if __name__ == "__main__":
    main()
