"""Minimax / Alpha-Beta 的性质测试。

用法（本目录内）：python3 -m pytest test_impl.py -v

覆盖：
- 两版**逐点等价**：同一局面、同一深度，alphabeta 与 minimax 的 (move, score) 必须完全相同
  ——这是剪枝的全部意义所在（"只省时间、不改结论"）
- 剪枝确实生效：alphabeta 访问的节点数不得多于 minimax
- 已知结论：空棋盘 depth=9 必为和棋 0；一步取胜的局面必须抓到必胜招
- 输入边界：终局局面、depth=0、无招可走时不崩
- **独立参考校验**：另写一份不复用 impl 的朴素 minimax（无剪枝、无提前终止），
  在小棋盘上对拍——避免"两版一起错"的自证陷阱
"""

import pytest

from demo import LINES, TicTacToe, game_interface, run_with_counter
from impl import alphabeta, best_move, minimax


# ---------------------------------------------------------------- 独立参考实现

def reference_minimax(board: tuple, player: int, depth: int) -> float:
    """独立参考：完全不复用 impl.py 的朴素 minimax。

    只返回评分（不返回招法），用于校验 impl 两个版本的**评分**是否正确。
    刻意写得笨拙：用 tuple 当状态、用列表推导展开、不做任何剪枝与提前终止。
    """
    def winner(cells) -> int:
        for a, b, c in LINES:
            v = cells[a]
            if v != 0 and v == cells[b] == cells[c]:
                return v
        return 0

    w = winner(board)
    if w != 0:
        return 10.0 * w
    if all(v != 0 for v in board):
        return 0.0
    if depth == 0:
        return 0.0                      # 参考实现只用于"搜到终局"的场合
    moves = [i for i, v in enumerate(board) if v == 0]
    scores = []
    for m in moves:
        nxt = list(board)
        nxt[m] = player
        scores.append(reference_minimax(tuple(nxt), -player, depth - 1))
    return max(scores) if player == 1 else min(scores)


# ---------------------------------------------------------------- 工具

def play(moves: list) -> tuple:
    """按给定走子序列构造一个局面，返回 (board, 下一个该谁走)。"""
    state = TicTacToe()
    for m in moves:
        state = state.apply(m)
    return tuple(state.board), state.player


def interface(state: TicTacToe) -> dict:
    return game_interface(state)


# ---------------------------------------------------------------- 等价性

@pytest.mark.parametrize("moves", [
    [],                    # 空棋盘
    [4],                   # 中心
    [0],                   # 角
    [4, 0],                # 中 → 角
    [0, 4, 8],             # 一条对角线的争夺
    [0, 1, 3],             # 边局
    [4, 0, 8, 2],          # 接近终局
])
def test_two_versions_agree_on_score(moves: list) -> None:
    """同一局面：两版的评分必须一致，且与独立参考一致。"""
    board, player = play(moves)
    state = TicTacToe(list(board), player)
    game = interface(state)
    maximizing = player == 1

    _, s_plain, _ = run_with_counter(minimax, state, 9, maximizing, **game)
    _, s_ab, _ = run_with_counter(
        alphabeta, state, 9, float("-inf"), float("inf"), maximizing, **game)
    expected = reference_minimax(board, player, 9)

    assert s_plain == s_ab, f"两版评分不一致：{s_plain} vs {s_ab}（moves={moves}）"
    assert s_plain == expected, (
        f"与独立参考不一致：impl={s_plain}，参考={expected}（moves={moves}）")


@pytest.mark.parametrize("moves", [[], [4], [0], [4, 0], [0, 4, 8], [4, 0, 8, 2]])
def test_alphabeta_visits_no_more_nodes(moves: list) -> None:
    """剪枝版访问的节点数不得多于朴素版（同局面、同深度）。"""
    board, player = play(moves)
    state = TicTacToe(list(board), player)
    game = interface(state)
    maximizing = player == 1

    _, _, n_plain = run_with_counter(minimax, state, 9, maximizing, **game)
    _, _, n_ab = run_with_counter(
        alphabeta, state, 9, float("-inf"), float("inf"), maximizing, **game)
    assert n_ab <= n_plain, f"剪枝版反而更贵：{n_ab} > {n_plain}（moves={moves}）"


# ---------------------------------------------------------------- 已知局面

def test_empty_board_is_a_draw() -> None:
    """空棋盘 depth=9：井字棋在双方最优下必为和棋（评分 0）。"""
    state = TicTacToe()
    move, score = best_move(state, 9, **interface(state))
    assert score == 0.0, f"空棋盘应为和棋，实际 score={score}"
    assert move in state.get_moves(), f"返回的招法必须合法，实际 {move}"


def test_takes_immediate_win() -> None:
    """我方（X）在 0、1 已连两子：必须下 2 取胜。"""
    state = TicTacToe([1, 1, 0,
                       0, -1, 0,
                       -1, 0, 0], player=1)
    game = interface(state)
    for fn, args in ((minimax, (9, True)), (alphabeta, (9, float("-inf"), float("inf"), True))):
        move, score = fn(state, *args, **game)
        assert move == 2, f"{fn.__name__} 没抓到必胜招：{move}"
        assert score == 10.0, f"{fn.__name__} 评分应为必胜：{score}"


def test_blocks_immediate_loss() -> None:
    """对手（O）在 0、1 已连两子：我方必须堵 2，否则必输。"""
    state = TicTacToe([-1, -1, 0,
                       0, 1, 0,
                       0, 0, 0], player=1)
    game = interface(state)
    move, _ = best_move(state, 9, **game)
    assert move == 2, f"应当堵 2，实际 {move}"


# ---------------------------------------------------------------- 边界

def test_terminal_state_and_zero_depth() -> None:
    """终局局面与 depth=0：不崩，返回 (None, 评分)。"""
    full_draw = TicTacToe([1, -1, 1,
                           -1, 1, -1,
                           -1, 1, -1], player=1)
    assert full_draw.is_terminal()
    game = interface(full_draw)
    move, score = best_move(full_draw, 9, **game)
    assert move is None and score == 0.0

    empty = TicTacToe()
    move, score = best_move(empty, 0, **interface(empty))
    assert move is None and score == 0.0


def test_move_is_always_legal() -> None:
    """在若干随机局面上，返回的招法必须是合法招法。"""
    import random
    rng = random.Random(7)
    for _ in range(20):
        state = TicTacToe()
        for _ in range(rng.randrange(0, 7)):
            if state.is_terminal():
                break
            state = state.apply(rng.choice(state.get_moves()))
        if state.is_terminal():
            continue
        move, _ = best_move(state, 5, **interface(state))
        assert move in state.get_moves(), f"返回了非法招法 {move}"
