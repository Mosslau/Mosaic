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

两个版本刻意不共用递归主体：`alphabeta` 是独立的一份实现（多出 alpha/beta 窗口），
两者的结果必须逐点相同——这正是 demo 与 test 要断言的东西。
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

    返回值第一项在"叶子/终局"处是 None——那一层不做决策，只回报评分；
    调用方（上一层）负责记录是哪个招法走到了这个评分。
    """
    if depth == 0 or is_terminal(state):
        return None, evaluate(state)

    moves = get_moves(state)
    if not moves:                      # 防御：无招可走（正常井字棋不会出现）
        return None, evaluate(state)

    best_move: Optional[Move] = None
    if maximizing:
        best_score = float("-inf")
        for move in moves:
            _, score = minimax(apply(state, move), depth - 1, False,
                               get_moves, apply, evaluate, is_terminal)
            if score > best_score:     # 严格大于：平手时保留先找到的招法（确定性的来源）
                best_score, best_move = score, move
    else:
        best_score = float("inf")
        for move in moves:
            _, score = minimax(apply(state, move), depth - 1, True,
                               get_moves, apply, evaluate, is_terminal)
            if score < best_score:
                best_score, best_move = score, move
    return best_move, best_score


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
    """带 Alpha-Beta 剪枝的极小极大：接口与 minimax 对齐，多出 (alpha, beta) 剪枝窗口。

    - `alpha`：max 这一层**已经能拿到**的最好分数（下界）
    - `beta` ：min 这一层**已经能保证**的最好分数（上界）
    - 一旦 `beta <= alpha`，当前分支的结果不可能改变祖先层的选择，剩余招法直接剪掉

    剪枝只影响"算了多少"，不影响"选出哪个"——返回值与 `minimax` 逐点相同（demo/test 断言）。
    """
    if depth == 0 or is_terminal(state):
        return None, evaluate(state)

    moves = get_moves(state)
    if not moves:
        return None, evaluate(state)

    best_move: Optional[Move] = None
    if maximizing:
        best_score = float("-inf")
        for move in moves:
            _, score = alphabeta(apply(state, move), depth - 1, alpha, beta, False,
                                 get_moves, apply, evaluate, is_terminal)
            if score > best_score:
                best_score, best_move = score, move
            alpha = max(alpha, best_score)
            if beta <= alpha:          # 剪枝：对方不会让我们走到这里
                break
    else:
        best_score = float("inf")
        for move in moves:
            _, score = alphabeta(apply(state, move), depth - 1, alpha, beta, True,
                                 get_moves, apply, evaluate, is_terminal)
            if score < best_score:
                best_score, best_move = score, move
            beta = min(beta, best_score)
            if beta <= alpha:
                break
    return best_move, best_score


def best_move(state: Any, depth: int, **game: Callable) -> tuple[Optional[Move], float]:
    """默认入口：走剪枝版。game 里传 get_moves / apply / evaluate / is_terminal。"""
    return alphabeta(
        state, depth, float("-inf"), float("inf"), True,
        get_moves=game["get_moves"], apply=game["apply"],
        evaluate=game["evaluate"], is_terminal=game["is_terminal"],
    )


if __name__ == "__main__":
    raise SystemExit("本文件是博弈搜索库，跑实验请执行：python3 demo.py")
