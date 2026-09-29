"""Minimax 与 Alpha-Beta 剪枝 — 手写实现（搜索求解器）

双人零和博弈的决策搜索：
- 极小极大：轮流取 max（我方）/ min（对方）的收益，深度限制 + 局面评估
- Alpha-Beta：剪掉不可能影响最终决策的分支，结果不变、节点数大幅下降

本目录的形态由"博弈搜索"决定，没有 fit/predict：
- impl.py  手写 minimax 与 alphabeta 两个版本（同一接口，demo 对比剪枝收益）
- demo.py  井字棋上双跑对比 + 可视化

对弈接口约定（demo.py 用井字棋实现并注入）：
    get_moves(state) -> list[Any]     可走招法
    apply(state, move) -> state       走子后的新状态
    evaluate(state) -> float          局面评分，正数对我方有利
    is_terminal(state) -> bool        是否终局
"""

from typing import Any, Callable, Optional

Move = Any


def minimax(
    state: Any,
    depth: int,
    maximizing: bool,
    get_moves: Callable,
    apply: Callable,
    evaluate: Callable,
    is_terminal: Callable,
) -> tuple[Optional[Move], float]:
    """朴素极小极大：返回 (最优招法, 局面评分)。

    参数：
        state: 当前局面
        depth: 剩余搜索深度
        maximizing: 当前层是否我方（取 max）
        get_moves / apply / evaluate / is_terminal: 对弈接口（见模块 docstring）
    """
    # TODO: 手写：终局或 depth=0 返回 (None, evaluate(state))；
    #   否则遍历 get_moves，对每个招法 apply 后递归，轮转 max/min 取极值
    raise NotImplementedError("TODO: 手写朴素 minimax")


def alphabeta(
    state: Any,
    depth: int,
    alpha: float,
    beta: float,
    maximizing: bool,
    get_moves: Callable,
    apply: Callable,
    evaluate: Callable,
    is_terminal: Callable,
) -> tuple[Optional[Move], float]:
    """带 Alpha-Beta 剪枝的极小极大：接口与 minimax 对齐，多出 (alpha, beta) 剪枝窗口。"""
    # TODO: 手写：在 minimax 基础上维护窗口，beta <= alpha 时剪掉剩余分支
    raise NotImplementedError("TODO: 手写 alpha-beta 剪枝")


def best_move(state: Any, depth: int, **game: Callable) -> tuple[Optional[Move], float]:
    """默认入口：走剪枝版。game 里传 get_moves / apply / evaluate / is_terminal。"""
    return alphabeta(
        state, depth, float("-inf"), float("inf"), True,
        get_moves=game["get_moves"], apply=game["apply"],
        evaluate=game["evaluate"], is_terminal=game["is_terminal"],
    )


if __name__ == "__main__":
    raise SystemExit("请先完成 minimax/alphabeta，再到 demo.py 跑实验")
