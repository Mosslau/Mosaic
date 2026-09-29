"""Minimax / Alpha-Beta demo：井字棋上朴素版 vs 剪枝版双跑对比。

对照逻辑：同一棋盘、同一深度、同一局面，
跑 impl.minimax 与 impl.alphabeta，对比 节点访问数 / 耗时 ——
结果应完全一致，剪枝收益（访问节点显著变少）由此量化。
"""

import time

from impl import minimax, alphabeta


class TicTacToe:
    """TODO: 井字棋：3x3 棋盘 + get_moves / apply / evaluate / is_terminal。"""

    def get_moves(self) -> list:
        raise NotImplementedError

    def apply(self, move) -> "TicTacToe":
        raise NotImplementedError

    def evaluate(self) -> float:
        raise NotImplementedError

    def is_terminal(self) -> bool:
        raise NotImplementedError


def run_with_counter(fn, state, *args, **kwargs) -> tuple:
    """TODO: 包一层计数器，返回 (move, score, nodes_visited)。"""
    raise NotImplementedError


def main() -> None:
    state = TicTacToe()
    game = {
        "get_moves": state.get_moves,
        "apply": lambda s, m: s.apply(m),
        "evaluate": state.evaluate,
        "is_terminal": state.is_terminal,
    }

    t0 = time.perf_counter()
    m_plain, score_plain, nodes_plain = run_with_counter(minimax, state, 9, True, **game)
    t_plain = time.perf_counter() - t0

    t0 = time.perf_counter()
    m_ab, score_ab, nodes_ab = run_with_counter(
        alphabeta, state, 9, float("-inf"), float("inf"), True, **game)
    t_ab = time.perf_counter() - t0

    print(f"{'':14} | {'minimax':>10} | {'alphabeta':>10}")
    print("-" * 42)
    print(f"{'move':14} | {str(m_plain):>10} | {str(m_ab):>10}")
    print(f"{'score':14} | {score_plain:>10.2f} | {score_ab:>10.2f}")
    print(f"{'nodes':14} | {nodes_plain:>10} | {nodes_ab:>10}")
    print(f"{'time_sec':14} | {t_plain:>10.4f} | {t_ab:>10.4f}")

    # TODO: 可视化（可选：剪枝比例随搜索深度的变化曲线），保存到本目录
    # 结论写回本目录 README.md 的「实验结果」一节


if __name__ == "__main__":
    main()
