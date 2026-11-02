"""朴素 Minimax 独立基线（外部真值）。

为什么单独一份：
- `impl.py` 里的 `minimax` 是"被剪枝版对照"的朴素版，但它与 `alphabeta` 同属一个模块；
  若两者一起写错，等价性测试会自洽地通过（自证陷阱）。
- 本文件刻意不复用 `impl.py` 的任何代码：tuple 当状态、列表推导展开、无剪枝、无提前终止，
  只返回评分，作为 Alpha-Beta 结果的**外部真值**。

对弈规则只依赖井字棋的 8 条胜负线，自己维护，不 import demo。
"""

from __future__ import annotations

LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
         (0, 3, 6), (1, 4, 7), (2, 5, 8),
         (0, 4, 8), (2, 4, 6))
WIN_SCORE = 10.0


def _winner(cells: tuple) -> int:
    for a, b, c in LINES:
        v = cells[a]
        if v != 0 and v == cells[b] == cells[c]:
            return v
    return 0


def reference_minimax(board: tuple, player: int, depth: int) -> float:
    """独立参考：只返回评分，用于校验 impl 两个版本的评分。"""
    w = _winner(board)
    if w != 0:
        return WIN_SCORE * w
    if all(v != 0 for v in board):
        return 0.0
    if depth == 0:
        return 0.0
    moves = [i for i, v in enumerate(board) if v == 0]
    scores = []
    for m in moves:
        nxt = list(board)
        nxt[m] = player
        scores.append(reference_minimax(tuple(nxt), -player, depth - 1))
    return max(scores) if player == 1 else min(scores)


if __name__ == "__main__":
    raise SystemExit("本文件是独立基线库，入口是 demo.py：uv run python demo.py")
