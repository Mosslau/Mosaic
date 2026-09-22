"""蒙特卡洛树搜索 MCTS — 手写实现（搜索求解器）

MCTS 是"模拟驱动的决策搜索"，四步循环：
- Selection：从根节点沿 UCB1 选最有价值的子节点
- Expansion：展开未完全探索的节点
- Simulation：从该节点随机走子到终局（rollout）
- Backpropagation：把结果回传，更新路径上各节点的访问次数与胜率

本目录的形态由"模拟搜索"决定，没有 fit/predict：
- impl.py     手写 MCTS（UCB1 + 随机 rollout）
- baseline.py 随机策略对照（MCTS 的决策质量从对比中量化）
- demo.py     井字棋上 MCTS vs 随机基线，迭代次数 → 胜率收敛曲线

对弈接口约定（demo.py 用井字棋实现并注入）：
    get_moves(state) -> list[Any]   可走招法
    apply(state, move) -> state     走子后的新状态
    is_terminal(state) -> bool      是否终局
    winner(state) -> Optional[int]  终局赢家（None=平局），用于判断谁赢得本次 rollout
"""

import random
from typing import Any, Callable, Optional

Action = Any


class MCTS:
    """蒙特卡洛树搜索。

    用法：
        mcts = MCTS(get_moves, apply, is_terminal, winner, rng=None)
        action = mcts.search(state, iterations=1000)
    """

    def __init__(
        self,
        get_moves: Callable,
        apply: Callable,
        is_terminal: Callable,
        winner: Callable,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.get_moves = get_moves
        self.apply = apply
        self.is_terminal = is_terminal
        self.winner = winner
        self.rng = rng or random

    def search(self, state: Any, iterations: int = 1000) -> Optional[Action]:
        """在给定局面下模拟 iterations 次，返回胜率最高的招法（无可走招法返回 None）。"""
        # TODO: 手写四步循环：
        #   1. 节点 = (state, 未探索招法列表, 访问数, 累计胜值)
        #   2. UCB1：argmax(胜率 + C * sqrt(ln(parent_visits) / visits))
        #   3. 随机 rollout 到终局，从当前视角判胜负（+1 / 0 / -1）
        #   4. 回传更新路径上每个节点的访问数与累计胜值
        raise NotImplementedError("TODO: 手写 MCTS 四步循环")


if __name__ == "__main__":
    raise SystemExit("请先完成 MCTS，再到 demo.py 跑实验")
