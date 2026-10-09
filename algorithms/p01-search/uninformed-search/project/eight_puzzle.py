"""迁移项目：迭代加深 IDS 与 IDA* 解 8 数码。

教学目录讲了 DFS / BFS / UCS 三者怎么换"先看谁"；本项目把这条线走到底——
当 BFS/UCS **内存扛不住**时怎么办。这正是 A* 实验「局限与延伸」里点名的那条路：
`open` 集可能指数膨胀 → 用**迭代加深**把内存压成线性。

两个算法（都不是新东西，而是已学内容的组合）：
  · **IDS**  = 反复限深的 DFS，深度上限 1,2,3,… 逐层加深
              → 内存线性（只有一条路径），代价是**重复搜索浅层**
  · **IDA*** = IDS + A* 的 h（8 数码用"曼哈顿距离和"）
              → 既线性内存，又用 h 大幅剪枝（这正是 A* 实验里 `h` 的价值）

三组实验：
  1. **可解性**：随机打乱的局面里，IDA* 与 IDS 是否都能解、且**深度相同**（都最优）
  2. **效率**：同一批局面上 IDA* 比 IDS 少展开多少节点（h 的收益）
  3. **内存对照**：与 BFS 比——三者都最优，但 BFS 的边界峰值会随深度爆炸

运行：cd algorithms/p01-search/uninformed-search/project && python3 eight_puzzle.py
依赖：只用标准库
"""

import random
import time
from collections import deque
from typing import Optional

GOAL = (1, 2, 3, 4, 5, 6, 7, 8, 0)          # 0 表示空格
MOVE_NAMES = {1: "上", -1: "下", 3: "左", -3: "右"}   # 空格移动方向


# ---------------------------------------------------------------- 局面工具

def blank_index(state: tuple) -> int:
    return state.index(0)


def neighbors(state: tuple) -> list[tuple]:
    """空格可移动后的所有局面（四方向，不越界）。

    用扁平下标 + 行列判断代替二维数组：8 数码的合法移动 = 空格与相邻格交换，
    行边界避免 2↔3、5↔6 之间的"跨行"移动。
    """
    i = blank_index(state)
    r, c = divmod(i, 3)
    out = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < 3 and 0 <= nc < 3:
            j = nr * 3 + nc
            nxt = list(state)
            nxt[i], nxt[j] = nxt[j], nxt[i]
            out.append(tuple(nxt))
    return out


def manhattan(state: tuple) -> int:
    """启发式 h：所有牌"到目标位置的曼哈顿距离"之和。

    可采纳（每一步最多让一块牌的距离减 1，而一次移动只动一块牌），
    且在 8 数码上**一致**——所以可以直接用 A* 的"首次到达即最优"口径。
    """
    total = 0
    for idx, tile in enumerate(state):
        if tile == 0:
            continue
        r, c = divmod(idx, 3)
        gr, gc = divmod(tile - 1, 3)          # 牌 tile 的目标位置
        total += abs(r - gr) + abs(c - gc)
    return total


def is_solvable(state: tuple) -> bool:
    """逆序数判据：忽略空格，逆序数为偶数则可解（3×3 的标准结论）。"""
    tiles = [t for t in state if t != 0]
    inversions = sum(1 for i in range(len(tiles)) for j in range(i + 1, len(tiles))
                     if tiles[i] > tiles[j])
    return inversions % 2 == 0


def scramble(steps: int, seed: int) -> tuple:
    """从目标局面随机走 `steps` 步生成局面（保证可解，且离目标不远）。"""
    rng = random.Random(seed)
    state = GOAL
    prev = None
    for _ in range(steps):
        options = [n for n in neighbors(state) if n != prev]
        prev, state = state, rng.choice(options)
    return state


# ---------------------------------------------------------------- 两个算法

def solve_ids(start: tuple, max_depth: int = 31) -> tuple:
    """迭代加深（IDS）：深度上限 1,2,3,… 逐层加深的 DFS。

    返回 (路径, 深度, 展开节点数)；解不出返回 (None, None, 展开数)。
    **内存线性**：任何时刻只有一条路径 + 递归栈。
    """
    expanded = 0

    def dfs(state: tuple, g: int, limit: int, path: list) -> Optional[list]:
        nonlocal expanded
        expanded += 1
        if state == GOAL:
            return list(path)
        if g == limit:
            return None
        for nxt in neighbors(state):
            if path and nxt == path[-1]:
                continue
            path.append(nxt)
            found = dfs(nxt, g + 1, limit, path)
            if found is not None:
                return found
            path.pop()
        return None

    for limit in range(max_depth + 1):
        found = dfs(start, 0, limit, [start])
        if found is not None:
            return found, len(found) - 1, expanded
    return None, None, expanded


def solve_ida_star(start: tuple, max_depth: int = 40) -> tuple:
    """IDA*：把 IDS 的"深度上限"换成"A* 的 f 上限"，逐轮提高。

    与 IDS 的差别只有一处：**用 `g + h` 做剪枝门槛**，而不是纯深度。
    这不是新算法，而是"A* 的启发式" + "迭代加深的内存优势"的组合——
    也正是 A* 实验「局限与延伸」里点名的 IDA*。

    返回 (路径, 深度, 展开节点数)。
    """
    expanded = 0
    threshold = manhattan(start)

    def search(state: tuple, g: int, threshold: float, path: list, prev) -> tuple:
        """返回 (路径 or None, 下一轮的最小超限 f 值)。"""
        nonlocal expanded
        expanded += 1
        f = g + manhattan(state)
        if f > threshold:
            return None, f
        if state == GOAL:
            return list(path), f
        minimum = float("inf")
        for nxt in neighbors(state):
            if nxt == prev:
                continue
            path.append(nxt)
            found, exceeded = search(nxt, g + 1, threshold, path, state)
            path.pop()
            if found is not None:
                return found, exceeded
            minimum = min(minimum, exceeded)
        return None, minimum

    while threshold <= max_depth:
        found, exceeded = search(start, 0, threshold, [start], None)
        if found is not None:
            return found, len(found) - 1, expanded
        if exceeded == float("inf"):
            break
        threshold = exceeded                    # 下一轮只放到"刚好超限"的那一档
    return None, None, expanded


def solve_bfs(start: tuple) -> tuple:
    """BFS（对照用）：最优但内存会爆——用来展示"为什么要迭代加深"。"""
    if start == GOAL:
        return [start], 0, 1, 1
    prev, dist = {start: None}, {start: 0}
    queue = deque([start])
    expanded = peak = 0
    while queue:
        peak = max(peak, len(queue))
        node = queue.popleft()
        expanded += 1
        if node == GOAL:
            path, cur = [], node
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            return path[::-1], dist[node], expanded, peak
        for nxt in neighbors(node):
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                prev[nxt] = node
                queue.append(nxt)
    return None, None, expanded, peak


# ---------------------------------------------------------------- 实验

def experiment_correctness(cases: list) -> list:
    """两者都要解出来，且**深度相同**（IDS 与 IDA* 都是最优算法）。"""
    print("== 实验一：可解性与最优性（同一批局面，两个算法深度必须相同） ==")
    print(f"{'局面（随机步数/种子）':>22} | {'深度':>4} | {'IDA* 展开':>10} | {'IDS 展开':>10} | {'加速':>7}")
    print("-" * 70)
    rows = []
    for steps, seed in cases:
        start = scramble(steps, seed)
        assert is_solvable(start)
        t0 = time.perf_counter()
        path_a, depth_a, exp_a = solve_ida_star(start)
        t_a = time.perf_counter() - t0
        t0 = time.perf_counter()
        path_b, depth_b, exp_b = solve_ids(start)
        t_b = time.perf_counter() - t0
        assert path_a is not None and path_b is not None, f"两个算法都必须解出：{start}"
        assert depth_a == depth_b, (
            f"深度不一致说明有一方不是最优：IDA* {depth_a} vs IDS {depth_b}（{start}）")
        rows.append((steps, seed, start, depth_a, exp_a, exp_b, t_a, t_b))
        print(f"{f'{steps} 步 / seed {seed}':>22} | {depth_a:>4} | {exp_a:>10,} | "
              f"{exp_b:>10,} | {exp_b / exp_a:>6.1f}×")
    return rows


def experiment_memory(cases: list) -> list:
    """内存对照：三者都最优，但 BFS 的边界峰值随深度爆炸。"""
    print("\n== 实验二：内存对照（同一批局面） ==")
    print(f"{'局面':>16} | {'深度':>4} | {'BFS 边界峰值':>12} | {'IDS/IDA* 边界峰值':>16}")
    print("-" * 62)
    rows = []
    for steps, seed in cases:
        start = scramble(steps, seed)
        path, depth, exp_bfs, peak_bfs = solve_bfs(start)
        # 迭代加深类算法的"边界"= 递归栈深度 = 当前路径长度，天然线性
        rows.append((start, depth, peak_bfs, depth + 1))
        print(f"{f'{steps} 步 / seed {seed}':>16} | {depth:>4} | {peak_bfs:>12,} | {depth + 1:>16,}")
    print("\n→ BFS 的边界峰值随深度**指数级**增长；迭代加深类的峰值 = 路径长度（线性）")
    return rows


def main() -> None:
    cases = [(6, 1), (8, 2), (10, 3), (12, 4), (14, 5)]
    rows = experiment_correctness(cases)
    experiment_memory(cases)

    total_a = sum(r[4] for r in rows)
    total_b = sum(r[5] for r in rows)
    print(f"\n结论：同一批 {len(rows)} 个局面，IDA* 共展开 {total_a:,} 个节点，"
          f"IDS 展开 {total_b:,} 个——**IDA* 只用了 IDS 的 1/{total_b / total_a:,.0f}**"
          f"（两者内存都是线性的，差别全在 h 的剪枝）")


if __name__ == "__main__":
    main()
