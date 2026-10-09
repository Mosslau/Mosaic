"""两个对照基线：纯随机，以及"一步贪心 + 挡招"的启发式策略。

为什么需要两个：
- **纯随机**是最弱的基线，用来回答"MCTS 会不会比瞎下强"（迭代很少时就能赢它）；
- **贪心挡招**强得多（能赢就赢、对手要赢就挡），用来回答"模拟次数到底有没有用"——
  只打随机的话，迭代 10 次与 2000 次的胜率都接近 100%，看不出收敛过程。
"""

import random
from typing import Any, Callable, Optional


def random_move(
    state: Any,
    get_moves: Callable,
    rng: Optional[random.Random] = None,
) -> Optional[Any]:
    """从当前局面的可走招法中随机选一个（无招法返回 None）。"""
    moves = get_moves(state)
    if not moves:
        return None
    picker = rng if rng is not None else random
    return picker.choice(moves)


def greedy_move(
    state: Any,
    get_moves: Callable,
    apply: Callable,
    winner: Callable,
    me: int,
    rng: Optional[random.Random] = None,
) -> Optional[Any]:
    """启发式基线：能一步赢就赢、对手下一步能赢就挡，否则随机。

    这个对手比随机强得多，是 MCTS"模拟次数→棋力"曲线的合适对手。
    """
    moves = get_moves(state)
    if not moves:
        return None

    for move in moves:                                  # 1) 我能一步赢
        if winner(apply(state, move)) == me:
            return move
    opponent = -me
    for move in moves:                                  # 2) 对手下一步能赢 → 挡
        nxt = apply(state, move)
        for reply in get_moves(nxt):
            if winner(apply(nxt, reply)) == opponent:
                return move
    picker = rng if rng is not None else random
    return picker.choice(moves)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用对比：python3 demo.py")
