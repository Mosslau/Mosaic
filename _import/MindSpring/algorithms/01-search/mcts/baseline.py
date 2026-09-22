"""随机策略对照实现

作为 MCTS 的基线：MCTS 每步的"模拟"就是随机走子，
所以用"纯随机选择"做对照最直观 —— MCTS 的决策质量从与它的对比中量化。
"""

import random
from typing import Any, Callable, Optional


def random_move(
    state: Any,
    get_moves: Callable,
    rng: Optional[random.Random] = None,
) -> Optional[Any]:
    """从当前局面的可走招法中随机选一个（无招法返回 None）。"""
    # TODO: rng.choice(get_moves(state))
    raise NotImplementedError("TODO: 随机选招")


if __name__ == "__main__":
    raise SystemExit("请先完成 random_move，由 demo.py 统一调用对比")
