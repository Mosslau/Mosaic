"""第 5 题参考解：用 A* 解八数码（8-puzzle），与 BFS 对拍。

状态用长度 9 的元组表示，0 是空格，目标为 123456780（按行读）。
启发式取"每块到目标位置的曼哈顿距离之和"——每次移动最多让这个和减少 1，
所以它永远不高估剩余步数（可采纳且一致）。

运行：
    cd algorithms/p01-search/a-star/exercises
    python3 sol-05-八数码.py
"""

from __future__ import annotations

import heapq
import itertools
import random
from collections import deque

GOAL = (1, 2, 3, 4, 5, 6, 7, 8, 0)
SIZE = 3


def neighbors(state: tuple[int, ...]):
    i = state.index(0)
    r, c = divmod(i, SIZE)
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < SIZE and 0 <= nc < SIZE:
            j = nr * SIZE + nc
            nxt = list(state)
            nxt[i], nxt[j] = nxt[j], nxt[i]
            yield tuple(nxt)


def manhattan_sum(state: tuple[int, ...]) -> int:
    total = 0
    for idx, value in enumerate(state):
        if value == 0:
            continue
        r, c = divmod(idx, SIZE)
        gr, gc = divmod(value - 1, SIZE)  # 目标里 value 的位置（0 在最后）
        total += abs(r - gr) + abs(c - gc)
    return total


def astar(start: tuple[int, ...]) -> tuple[int, list[tuple[int, ...]]]:
    order = itertools.count()
    g = {start: 0}
    came: dict[tuple[int, ...], tuple[int, ...]] = {}
    heap = [(manhattan_sum(start), next(order), start)]
    while heap:
        _, _, state = heapq.heappop(heap)
        if state == GOAL:
            path = [state]
            while state in came:
                state = came[state]
                path.append(state)
            return g[GOAL], path[::-1]
        for nb in neighbors(state):
            ng = g[state] + 1
            if ng < g.get(nb, 1 << 30):
                g[nb] = ng
                came[nb] = state
                heapq.heappush(heap, (ng + manhattan_sum(nb), next(order), nb))
    raise AssertionError("八数码从任意可解状态都应能到达目标")


def bfs(start: tuple[int, ...]) -> int:
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        state, dist = queue.popleft()
        if state == GOAL:
            return dist
        for nb in neighbors(state):
            if nb not in seen:
                seen.add(nb)
                queue.append((nb, dist + 1))
    return -1


def scramble(moves: int, rng: random.Random) -> tuple[int, ...]:
    """从目标状态倒着走 moves 步——保证可解。"""
    state = GOAL
    last = None
    for _ in range(moves):
        options = [nb for nb in neighbors(state) if nb != last]
        nxt = rng.choice(options)
        last, state = state, nxt
    return state


def main() -> None:
    print("八数码：A*（曼哈顿距离和）vs BFS（乱序 6–9 步，5 个固定种子）")
    print(f"{'局面':<28} | {'乱序步数':>8} | {'A* 步数':>7} | {'BFS 步数':>8}")
    print("-" * 66)
    for seed in range(5):
        moves = 6 + seed % 4
        start = scramble(moves, random.Random(seed))
        a_steps, path = astar(start)
        b_steps = bfs(start)
        assert a_steps == b_steps, f"seed={seed}: A* {a_steps} != BFS {b_steps}"
        assert path[0] == start and path[-1] == GOAL
        assert len(path) - 1 == a_steps
        print(f"{''.join(map(str, start)):<28} | {moves:>8} | {a_steps:>7} | {b_steps:>8}")
    print("-" * 66)
    print("五个局面 A* 与 BFS 步数全部一致；启发式可采纳：每步最多让'距离和'减少 1。")


if __name__ == "__main__":
    main()
