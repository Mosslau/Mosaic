"""Minimax / Alpha-Beta demo：井字棋上朴素版 vs 剪枝版双跑对比。

对照逻辑：同一棋盘、同一深度、同一局面，
跑 impl.minimax 与 impl.alphabeta，对比 节点访问数 / 耗时 ——
结果应完全一致，剪枝收益（访问节点显著变少）由此量化。

三个实验：
1. 主对照：空棋盘、depth=9（搜到终局）——两版结论必须一致，剪枝只省工作量
2. 剪枝收益随深度：depth=1..9 逐档扫，节点数曲线
3. 招法顺序的影响：把首选招法换一下，看 alpha-beta 的收益能差多少

约定：**一个"访问节点" = 一次 `is_terminal()`**（每次进入递归的第一件事就是判终局）。
不计"进入状态数"而计这个，是因为它同时被朴素版与剪枝版调用，口径可比。

运行：cd algorithms/p01-search/minimax-alphabeta && python3 demo.py
"""

import copy
import time
from typing import Callable

from impl import alphabeta, minimax

# 井字棋的胜负线（行 / 列 / 两条对角线）
LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
         (0, 3, 6), (1, 4, 7), (2, 5, 8),
         (0, 4, 8), (2, 4, 6))

X_PLAYER = 1     # 我方，永远是 max 层
O_PLAYER = -1    # 对手，min 层
WIN_SCORE = 10.0  # 终局评分：赢 +10 / 输 -10 / 平 0


class TicTacToe:
    """井字棋局面：3×3 棋盘 + 当前该谁走。**不可变**——apply 返回新对象。

    不可变很关键：搜索会并行探索几百个分支，若 apply 就地改棋盘，
    兄弟分支会互相污染，算出来的招法就不可信了。
    """

    def __init__(self, board: list | None = None, player: int = X_PLAYER) -> None:
        self.board = list(board) if board is not None else [0] * 9
        self.player = player

    def winner(self) -> int:
        """返回胜者（1 / -1）；无人获胜返回 0。"""
        for a, b, c in LINES:
            v = self.board[a]
            if v != 0 and v == self.board[b] == self.board[c]:
                return v
        return 0

    def is_terminal(self) -> bool:
        return self.winner() != 0 or all(v != 0 for v in self.board)

    def get_moves(self) -> list:
        """空位列表，按格子编号升序——顺序固定，结果才可复现。"""
        return [i for i, v in enumerate(self.board) if v == 0]

    def apply(self, move: int) -> "TicTacToe":
        nxt = copy.copy(self)                 # 浅拷贝足够：board 不共享（下面重新构造）
        nxt.board = self.board.copy()
        nxt.board[move] = self.player
        nxt.player = -self.player
        return nxt

    def evaluate(self) -> float:
        """**终局评分**：赢 +10 / 输 -10 / 平 0。只在终局有意义。"""
        w = self.winner()
        return 0.0 if w == 0 else WIN_SCORE * w

    # ---- render 只用于打印，不属于对弈接口 ----
    def render(self) -> str:
        glyph = {1: "X", -1: "O", 0: "."}
        rows = ["".join(glyph[v] for v in self.board[i:i + 3]) for i in (0, 3, 6)]
        return " / ".join(rows)


# ------------------------------------------------------------------ 计数与计时


def visit_counter(is_terminal: Callable) -> tuple[Callable, list]:
    """把 is_terminal 包成"计数版"，返回 (包装后函数, 计数器列表)。"""
    counter = [0]

    def counted(state) -> bool:
        counter[0] += 1
        return is_terminal(state)

    return counted, counter


def game_interface(state: TicTacToe, order_by: Callable | None = None) -> dict:
    """构造对弈接口字典；order_by 给定时对招法排序（实验三用）。"""
    if order_by is None:
        return {
            "get_moves": lambda s: s.get_moves(),
            "apply": lambda s, m: s.apply(m),
            "evaluate": lambda s: s.evaluate(),
            "is_terminal": lambda s: s.is_terminal(),
        }
    return {
        "get_moves": lambda s: order_by(s, s.get_moves()),
        "apply": lambda s, m: s.apply(m),
        "evaluate": lambda s: s.evaluate(),
        "is_terminal": lambda s: s.is_terminal(),
    }


def run_with_counter(fn, state, *args, **kwargs) -> tuple:
    """跑一次搜索，返回 (move, score, nodes_visited)。

    做法：把传入的 is_terminal 换成计数版——搜索每进入一个状态都会先判终局，
    因此计数即"访问过的状态数"，且朴素版与剪枝版口径一致。
    """
    game = dict(kwargs)
    counted, counter = visit_counter(game["is_terminal"])
    game["is_terminal"] = counted
    result = fn(state, *args, **game)
    return result[0], result[1], counter[0]


def bench(fn, state, *args, repeats: int = 5, **kwargs) -> tuple:
    """重复跑取中位数：返回 (move, score, nodes, 中位耗时秒, [min, max] 毫秒)。"""
    samples, result = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = run_with_counter(fn, state, *args, **kwargs)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    median = samples[len(samples) // 2]
    return result[0], result[1], result[2], median, [samples[0], samples[-1]]


# ------------------------------------------------------------------ 实验


def experiment_main() -> tuple:
    """实验一：空棋盘、depth=9，朴素版 vs 剪枝版。"""
    print("== 实验一：空棋盘 3×3 井字棋，depth=9（搜到终局） ==")
    state = TicTacToe()
    game = game_interface(state)

    m_plain, s_plain, n_plain, t_plain, r_plain = bench(minimax, state, 9, True, **game)
    m_ab, s_ab, n_ab, t_ab, r_ab = bench(
        alphabeta, state, 9, float("-inf"), float("inf"), True, **game)

    assert m_plain == m_ab and s_plain == s_ab, (
        f"两版结论不一致：朴素 ({m_plain}, {s_plain}) vs 剪枝 ({m_ab}, {s_ab})")

    print(f"{'':14} | {'minimax':>10} | {'alphabeta':>10}")
    print("-" * 42)
    print(f"{'move':14} | {str(m_plain):>10} | {str(m_ab):>10}")
    print(f"{'score':14} | {s_plain:>10.1f} | {s_ab:>10.1f}")
    print(f"{'nodes':14} | {n_plain:>10} | {n_ab:>10}")
    print(f"{'time_ms(中位)':14} | {t_plain:>10.2f} | {t_ab:>10.2f}")
    saved = 1 - n_ab / n_plain
    print(f"结论：结论相同（move={m_plain}、score={s_plain:.1f}），"
          f"剪枝少访问 {n_plain - n_ab} 个节点（{saved:.1%}）")
    print(f"      耗时区间：朴素 [{r_plain[0]:.1f}–{r_plain[1]:.1f}] ms，"
          f"剪枝 [{r_ab[0]:.1f}–{r_ab[1]:.1f}] ms（单次 <100ms，只作量级参考）")
    return state, game, (m_plain, s_plain, n_plain, t_plain), (m_ab, s_ab, n_ab, t_ab)


def experiment_depth_profile(state: TicTacToe, game: dict) -> list:
    """实验二：剪枝收益随搜索深度变化。"""
    print("\n== 实验二：剪枝收益随搜索深度（同一空棋盘，depth=1..9） ==")
    print(f"{'depth':>6} | {'minimax 节点':>13} | {'alphabeta 节点':>14} | {'省下':>8} | {'两版一致':>8}")
    print("-" * 62)
    rows = []
    for depth in range(1, 10):
        _, s_p, n_p, *_ = bench(minimax, state, depth, True, repeats=3, **game)
        _, s_a, n_a, *_ = bench(alphabeta, state, depth, float("-inf"), float("inf"),
                                True, repeats=3, **game)
        same = (s_p == s_a)
        rows.append((depth, n_p, n_a, same))
        print(f"{depth:>6} | {n_p:>13,} | {n_a:>14,} | "
              f"{1 - n_a / n_p:>7.1%} | {'✓' if same else '✗':>8}")
    assert all(r[3] for r in rows), "存在两版评分不一致的深度档"
    return rows


def shallow_order(shallow_depth: int = 2, reverse: bool = False,
                  extra: list | None = None) -> Callable:
    """返回一个"按浅层搜索值排序"的 order 函数（实验三用）。

    这是真实引擎里的标准做法（浅层搜索 / 置换表 / 杀手招法）：**先粗算一遍，
    把看起来好的招法排在前面**，让 alpha-beta 尽早收窄窗口。

    `reverse=True` 故意反过来（先试看起来差的），用来造最坏顺序。
    `extra` 非空时把排序自己的访问量累加进去（实验三把它作为"排序开销"单列）。
    """
    def order(state: TicTacToe, moves: list) -> list:
        game = game_interface(state)
        scores = {}
        for move in moves:
            # 浅层搜索的访问量不进主计数：它属于"排序开销"，实验三里单独报
            _, score, extra_visits = run_with_counter(
                alphabeta, state.apply(move), shallow_depth,
                float("-inf"), float("inf"), state.player != X_PLAYER, **game)
            if extra is not None:
                extra[0] += extra_visits
            scores[move] = score
        # 并列时用格子编号做确定性 tie-break，保证结果可复现
        if reverse:
            return sorted(moves, key=lambda m: (scores[m], m))
        return sorted(moves, key=lambda m: (-scores[m], m))
    return order


def experiment_move_order(state: TicTacToe) -> list:
    """实验三：招法顺序对 alpha-beta 的影响（同一局面、同一深度、结论必须一致）。

    alpha-beta 的剪枝量**理论上依赖遍历顺序**：先看到的招法越好，越早收窄窗口。
    这里对比三种顺序，并如实报告"排序本身的搜索开销"：

      - 朴素顺序：格子编号升序，不排序（排序开销 0）
      - 好招优先：按浅层 depth=2 搜索值降序
      - 坏招优先：反向 —— 最坏情况
    """
    print("\n== 实验三：招法顺序如何影响剪枝（空棋盘，depth=9） ==")
    print(f"{'顺序':<22} | {'move':>4} | {'score':>5} | {'主搜索访问':>10} | {'排序额外访问':>12}")
    print("-" * 68)
    plain_extra, good_extra, bad_extra = [0], [0], [0]
    cases = [
        ("朴素顺序（不排序）", game_interface(state), plain_extra),
        ("好招优先（浅层 depth=2）",
         game_interface(state, order_by=shallow_order(2, False, good_extra)), good_extra),
        ("坏招优先（反向）",
         game_interface(state, order_by=shallow_order(2, True, bad_extra)), bad_extra),
    ]
    rows = []
    for name, game, extra in cases:
        move, score, nodes, t_ms, _ = bench(
            alphabeta, state, 9, float("-inf"), float("inf"), True, repeats=3, **game)
        rows.append((name, move, score, nodes, extra[0]))
        print(f"{name:<22} | {move:>4} | {score:>5.1f} | {nodes:>10,} | {extra[0]:>12,}")

    assert len({(r[1], r[2]) for r in rows}) == 1, (
        f"三种顺序的结论应当完全一致，实际 {[(r[1], r[2]) for r in rows]}")
    print("  三种顺序的**结论完全相同**（move/score 一致）——顺序只改'算了多少'，不改'选中哪个'")
    best = min(r[3] for r in rows)
    worst = max(r[3] for r in rows)
    print(f"  但访向量差 {worst - best:,} 个（{best:,} ↔ {worst:,}，相对最差省 {1 - best / worst:.1%}）")
    print("  代价：排序键靠「每个节点都重算一遍浅层搜索」得来（见「排序额外访问」列）——")
    print("  这份开销远大于它省下的主搜索量。**结论：顺序能剪更多，但浅层重算的代价更大**；")
    print("  真实引擎先用置换表 / 迭代加深把这些浅层结果**复用**掉，排序才真正划算。")
    return rows


def main() -> None:
    state, game, plain, ab = experiment_main()
    experiment_depth_profile(state, game)
    experiment_move_order(state)
    print(f"\n（棋盘记法：{state.render()}，X = 我方先手）")


if __name__ == "__main__":
    main()
