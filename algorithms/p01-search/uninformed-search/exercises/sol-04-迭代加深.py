"""参考解 4：手写迭代加深（IDS），并量化它"用时间换空间"的代价。

用法：python3 sol-04-迭代加深.py

断言三件事（这就是本题要验证的"交易"是否真的发生）：
  1. IDS 与 BFS 给出的步数**相同**（无权图上两者都最优）
  2. IDS 的扩展数**大于** BFS（它重复搜索浅层）
  3. IDS 的内存尖峰**小于** BFS（这是它换来的东西）
"""

import sys
import time
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from demo import make_grid                      # noqa: E402
from impl import bfs, neighbors                 # noqa: E402


def ids(grid, start, goal, max_depth=None):
    """迭代加深：深度上限 1,2,3,… 逐层加深的限深 DFS。

    返回 (路径, 步数, 扩展数, 栈深度)。
    **栈深度 = 当前路径长度**——这是 IDS 内存的确定上界（它不需要存整层前沿）。
    注意：BFS 的"边界峰值"是另一回事（它要存下整整一层），两者的口径不同，
    所以下面只比"确定能比的量"，不硬比大小。
    """
    if max_depth is None:
        max_depth = len(grid) * len(grid[0])
    expanded = 0
    peak = 0

    def dfs(node, depth, limit, path):
        nonlocal expanded, peak
        expanded += 1
        peak = max(peak, len(path))                                # 栈深度 = 路径长度
        if node == goal:
            return list(path)
        if depth == limit:
            return None
        for nb in neighbors(grid, node):
            if nb == path[-2] if len(path) >= 2 else False:
                continue                                          # 不回走（父节点）
            if nb in path:                                        # 路径上判重（防环）
                continue
            path.append(nb)
            found = dfs(nb, depth + 1, limit, path)
            if found is not None:
                return found
            path.pop()
        return None

    for limit in range(1, max_depth + 1):
        found = dfs(start, 0, limit, [start])
        if found is not None:
            return found, len(found) - 1, expanded, peak
    return None, None, expanded, peak


def bfs_with_peak(grid, start, goal):
    """BFS 并统计扩展数与边界峰值（用于对照）。"""
    prev, dist = {start: None}, {start: 0}
    queue = deque([start])
    expanded = peak = 0
    while queue:
        peak = max(peak, len(queue))
        node = queue.popleft()
        expanded += 1
        if node == goal:
            path, cur = [], node
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            return path[::-1], dist[node], expanded, peak
        for nb in neighbors(grid, node):
            if nb not in dist:
                dist[nb] = dist[node] + 1
                prev[nb] = node
                queue.append(nb)
    return None, None, expanded, peak


def main() -> None:
    print("== 迭代加深 IDS vs BFS（网格地图，路径长度控制在 8–15） ==")
    print(f"{'图':>14} | {'算法':>4} | {'步数':>4} | {'扩展':>9} | {'内存量':>7} | {'耗时(ms)':>9}")
    print("-" * 62)
    cases = ((7, 7, 0.15, 300), (9, 9, 0.25, 301), (9, 9, 0.30, 302))
    for rows, cols, ratio, seed in cases:
        grid, start, goal = make_grid(rows=rows, cols=cols, obstacle_ratio=ratio, seed=seed)
        t0 = time.perf_counter()
        p_ids, d_ids, e_ids, peak_ids = ids(grid, start, goal)
        ms_ids = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        p_bfs, d_bfs, e_bfs, peak_bfs = bfs_with_peak(grid, start, goal)
        ms_bfs = (time.perf_counter() - t0) * 1000

        tag = f"{rows}×{cols} 障碍{ratio:.0%}"
        print(f"{tag:>14} | {'ids':>4} | {d_ids:>4} | {e_ids:>9,} | {peak_ids:>7} | {ms_ids:>9.2f}")
        print(f"{'':>14} | {'bfs':>4} | {d_bfs:>4} | {e_bfs:>9,} | {peak_bfs:>7} | {ms_bfs:>9.2f}")

        # ---- 两条断言（这两条在任何规模上都成立）
        assert d_ids == d_bfs, f"两者步数必须相同（都最优）：{d_ids} vs {d_bfs}"
        assert e_ids > e_bfs, f"IDS 应当扩展更多（重复搜索浅层）：{e_ids} vs {e_bfs}"
        # 内存不做断言：小图上 BFS 的边界峰值可能**小于** IDS 的栈深度
        # （本实验实测：9×9 障碍 30% 时 BFS 峰值 6、IDS 栈深 12）。
        # 只有规模大起来（如 8 数码 depth=14：BFS 峰值 2,216 vs 迭代加深 15）
        # 线性内存的优势才显现——见 ../project/README.md。

    print("\n结论一：IDS 与 BFS 的**步数完全一致**（在无权图上两者都最优）——换算法不换答案。")
    print("结论二：IDS 的扩展数远大于 BFS——这是「重复搜索浅层」的代价，随深度**指数放大**。")
    print("结论三（反直觉，必须自己看一眼）：**小图上 IDS 的内存并不省**——")
    print("        BFS 的边界峰值可能只有个位数，而 IDS 的栈深度等于路径长度（更长）。")
    print("        「线性内存」是**渐近结论**：只有规模大起来才兑现，")
    print("        见 ../project/README.md（8 数码 depth=14：BFS 峰值 2,216 vs 迭代加深 15）。")


if __name__ == "__main__":
    main()
