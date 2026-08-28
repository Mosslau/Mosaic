"""MCTS demo：井字棋上 MCTS vs 随机基线，迭代次数 → 胜率收敛曲线。

对照逻辑：固定随机种子，MCTS（迭代 N 次）先手对战随机策略 G 局，
统计胜率随 N 的变化 —— "模拟越多决策越强"的收敛效果由此量化。
"""

from impl import MCTS
from baseline import random_move


class TicTacToe:
    """TODO: 井字棋（与 minimax 目录同一约定：get_moves / apply / is_terminal / winner）。"""


def win_rate(iterations: int, games: int = 200, seed: int = 42) -> float:
    """TODO: 跑 G 局，返回 MCTS 先手胜率（平局口径在 README 里说明）。"""
    raise NotImplementedError


def main() -> None:
    for iters in [10, 50, 100, 500, 1000, 2000]:
        rate = win_rate(iters)
        print(f"iterations={iters:>5}  win_rate={rate:.2%}")

    # TODO: matplotlib 画 迭代次数 vs 胜率 收敛曲线，保存到本目录
    # 结论写回本目录 README.md 的「实验结果」一节


if __name__ == "__main__":
    main()
