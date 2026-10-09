"""参考解 5：新约束下的搜索——"总代价不超过预算 B 的前提下，步数最少"。

用法：python3 sol-05-迁移.py

为什么 BFS / UCS 都不能直接用：
  · BFS 只按步数排队，完全不知道代价 → 它给的最短路可能直接超预算
  · UCS 只按总代价排队 → 它给的是"代价最小"，不是"步数最少"

关键改动：**状态从"位置"扩展成"(位置, 已花代价)"**。
只记位置的话，"到过这里"会把"花费更少但步数更多"的路判为重复而丢掉——
而它可能正是预算内步数更多的关键。
"""

import heapq
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import neighbors                       # noqa: E402

TERRAIN_MIN, TERRAIN_MAX = 1, 6


def make_grid():
    """手工对照图：上排是"贵但短"的直穿路，下排是"便宜但绕远"的走廊。

        列 0    1    2    3
    行0  1   11   11   11      ← 直穿：3 步，代价 11+11+11 = 33（起点不计费）
    行1  1    1    1    1      ← 绕远：5 步，代价 1+1+1+1+11 = 15

    为什么要手工设计而不是随机生成：随机小图上几乎总能找到"又短又便宜"的路，
    预算就永远不起作用（本项目实测过：4 组随机图 + 3 组手工图都不触发）。
    只有"短 = 贵、长 = 便宜"这种**必须权衡**的结构，才能让约束改变答案。
    """
    grid = [[1, 11, 11, 11],
            [1,  1,  1,  1]]
    return grid, (0, 0), (0, 3)


def solve_with_budget(grid, start, goal, budget):
    """状态 = (位置, 已花代价)，按"已花代价"做 UCS；在预算内取步数最少的解。

    返回 (步数, 路径, 扩展的状态数)；无解返回 (None, None, 扩展数)。
    代价是整数（1–6），所以状态空间是 位置 × 可能的代价取值 —— 这就是新约束的代价。
    """
    def enter_cost(node):
        return float(grid[node[0]][node[1]])

    init = (start, 0.0)
    dist = {init: 0.0}                # 该状态的最小已花代价（= 状态本身的第二维）
    steps = {init: 0}
    prev = {init: None}
    heap = [(0.0, 0, init)]           # (已花代价, 步数, 状态)：先比代价，再比步数
    expanded = 0
    best_state = None                 # (步数, 状态)：只记最优的那个，最后统一重建路径
    best_steps = None
    while heap:
        cost, step, state = heapq.heappop(heap)
        if cost > dist.get(state, float("inf")):
            continue
        expanded += 1
        node, _ = state
        if node == goal:
            # 堆按代价排序，所以第一次弹出的终点不一定步数最少；
            # 这里不提前返回，而是记录所有"预算内到达终点"的解，最后取步数最小的。
            if best_steps is None or step < best_steps:
                best_steps, best_state = step, state
            continue
        for nb in neighbors(grid, node):
            ncost = cost + enter_cost(nb)
            if ncost > budget:
                continue                       # 预算剪枝：超了就根本不进边界
            nstate = (nb, ncost)
            nstep = step + 1
            if ncost < dist.get(nstate, float("inf")):
                dist[nstate] = ncost
                steps[nstate] = nstep
                prev[nstate] = state
                heapq.heappush(heap, (ncost, nstep, nstate))
            elif ncost == dist.get(nstate) and nstep < steps.get(nstate, 10**9):
                steps[nstate] = nstep          # 同代价下保留步数更少的
                prev[nstate] = state
    if best_state is None:
        return None, None, expanded
    path, cur = [], best_state
    while cur is not None:
        path.append(cur[0])
        cur = prev[cur]
    return best_steps, path[::-1], expanded


def render(grid, path):
    marks = {p: "*" for p in path[1:-1]}
    marks[path[0]] = "S"
    marks[path[-1]] = "G"
    out = []
    for r in range(len(grid)):
        row = []
        for c in range(len(grid[0])):
            if grid[r][c] == -1:
                row.append("  #")
            elif (r, c) in marks:
                row.append(f"  {marks[(r, c)]}")
            else:
                row.append(f"{grid[r][c]:>3}")
        out.append("".join(row))
    return "\n".join(out)


def main() -> None:
    grid, start, goal = make_grid()
    print("== 手工对照图（数字 = 进入代价） ==")
    print(render(grid, [start, goal]))
    print("\n候选路径：")
    print("  上排直穿：3 步，代价 33（贵）")
    print("  下排绕远：5 步，代价 15（便宜）")

    print(f"\n{'预算 B':>6} | {'步数':>4} | {'总代价':>6} | {'扩展状态':>8} | 说明")
    print("-" * 58)
    results = {}
    for budget in (10, 15, 34):
        steps, path, expanded = solve_with_budget(grid, start, goal, budget)
        if steps is None:
            results[budget] = None
            print(f"{budget:>6} | {'无解':>4} | {'—':>6} | {expanded:>8} | "
                  f"两条路都超预算")
            continue
        total = sum(grid[r][c] for r, c in path[1:])
        results[budget] = (steps, path, total, expanded)
        note = "被迫走长路（短路超预算）" if steps == 5 else "走短路（预算够）"
        print(f"{budget:>6} | {steps:>4} | {total:>6} | {expanded:>8} | {note}")

    # ---- 三条断言：预算必须真的改变答案
    assert results[10] is None, "B=10 连便宜的那条都走不通，应当无解"
    s15, p15, c15, _ = results[15]
    s34, p34, c34, _ = results[34]
    assert s15 == 5 and c15 == 15, f"B=15 时应当走 5 步 / 代价 15 的长路：{s15} 步 / {c15}"
    assert s34 == 3 and c34 == 33, f"B=34 时应当走 3 步 / 代价 33 的短路：{s34} 步 / {c34}"
    assert s34 < s15, "预算放松后步数应当变小（约束更松，可行解更多）"

    print(f"\nB=15 的路径：{' → '.join(f'({r},{c})' for r, c in p15)}")
    print(f"B=34 的路径：{' → '.join(f'({r},{c})' for r, c in p34)}")
    print(f"\n结论一（单调性）：B 从 15 放松到 34，步数 {s15} → {s34}——"
          f"可行解集合变大，最小值只能更小或不变 ✓")
    print("结论二（两条路不同）：预算紧时**被迫**走那条更长的便宜路；")
    print("        预算松时才走得起那条更短的贵路——**同一个图，两个不同的最优决策**。")
    print("结论三（状态空间）：状态是 `(位置, 已花代价)`，扩展状态数随预算放宽而增长"
          f"（{results[15][3]} → {results[34][3]}）——**约束越松，要找的状态越多**。")


if __name__ == "__main__":
    main()
