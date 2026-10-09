"""迁移项目：深度受限的博弈搜索（四子连珠，棋盘与连珠数可配）。

教学目录（`../impl.py` + `../demo.py`）用的是 3×3 井字棋——它**最多 9 手、能搜到终局**，
于是 `evaluate()` 只要判胜负就够，搜索本身不依赖任何"估计"。

本项目换一个**搜不到终局**的棋类，补上教学版缺的那两块：

1. **深度限制 + 启发式评估**：搜到 `depth` 就停，用 `evaluate()` 估这个局面值多少分；
2. **评估质量 vs 搜索深度**：哪个更决定棋力？用三组自对弈实验分别量化。

搜索本体**不在这里重写**——直接调用教学目录的 `impl.alphabeta`（同一份代码，
本项目只换棋类与评估函数），这也是"迁移"该有的样子：算法不动，接口换一个。

运行：cd algorithms/p01-search/minimax-alphabeta/project && python3 connect4_search.py
依赖：只用标准库（不需要 numpy / matplotlib）
"""

import random
import sys
import time
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from impl import alphabeta  # noqa: E402

X_PLAYER, O_PLAYER = 1, -1
WIN_SCORE = 1000.0


def _lines(size: int, win_len: int) -> list:
    """所有取胜线：横 / 竖 / 两条斜。"""
    out = []
    for r in range(size):
        for c in range(size - win_len + 1):
            out.append(tuple(r * size + c + k for k in range(win_len)))
    for c in range(size):
        for r in range(size - win_len + 1):
            out.append(tuple((r + k) * size + c for k in range(win_len)))
    for r in range(size - win_len + 1):
        for c in range(size - win_len + 1):
            out.append(tuple((r + k) * size + c + k for k in range(win_len)))
            out.append(tuple((r + k) * size + c + win_len - 1 - k for k in range(win_len)))
    return out


class Board:
    """四子连珠局面：`size`×`size` 棋盘、`win_len` 连珠取胜。

    **不可变**：`apply` 返回新对象——搜索会同时探索许多分支，就地改棋盘会让它们互相污染。
    """

    size = 5
    win_len = 4
    lines: list = _lines(5, 4)

    def __init__(self, cells: Optional[list] = None, player: int = X_PLAYER) -> None:
        self.cells = list(cells) if cells is not None else [0] * (self.size ** 2)
        self.player = player

    @classmethod
    def configure(cls, size: int, win_len: int) -> type:
        cls.size, cls.win_len = size, win_len
        cls.lines = _lines(size, win_len)
        return cls

    def winner(self) -> int:
        for ln in self.lines:
            v = self.cells[ln[0]]
            if v != 0 and all(self.cells[i] == v for i in ln):
                return v
        return 0

    def is_terminal(self) -> bool:
        return self.winner() != 0 or all(v != 0 for v in self.cells)

    def get_moves(self) -> list:
        return [i for i, v in enumerate(self.cells) if v == 0]

    def apply(self, move: int) -> "Board":
        nxt = Board(self.cells, -self.player)
        nxt.cells[move] = self.player
        return nxt

    def evaluate(self) -> float:
        """**启发式评估**：每条取胜线按"我占几子 / 对手占几子"折算，3 的幂做权重。

        这是教学版缺失的那一块——搜不到终局时只能靠它估。权重取 3 的幂，
        含义是"三子连线远比二子连线重要"，同时避免不同长度之间互相抵消。
        """
        w = self.winner()
        if w != 0:
            return WIN_SCORE * w
        score = 0.0
        for ln in self.lines:
            vals = [self.cells[i] for i in ln]
            mine, theirs = vals.count(X_PLAYER), vals.count(O_PLAYER)
            if mine and theirs:
                continue                     # 这条线双方都占了 → 已废
            if mine:
                score += 3.0 ** mine
            elif theirs:
                score -= 3.0 ** theirs
        return score

    def render(self) -> str:
        glyph = {1: "X", -1: "O", 0: "."}
        return "\n".join(
            "".join(glyph[self.cells[r * self.size + c]] for c in range(self.size))
            for r in range(self.size))


# ---------------------------------------------------------------- 对弈接口与计数

def interface(evaluate: Optional[Callable] = None) -> dict:
    """把棋类接口交给教学目录的 impl（**同一份搜索代码**）。"""
    return {
        "get_moves": lambda s: s.get_moves(),
        "apply": lambda s, m: s.apply(m),
        "evaluate": (lambda s: s.evaluate()) if evaluate is None else evaluate,
        "is_terminal": lambda s: s.is_terminal(),
    }


def count_nodes(fn, state, *args, **kwargs) -> tuple:
    """跑一次搜索并统计访问节点数（口径与教学版一致：包 is_terminal）。"""
    game = dict(kwargs)
    counter = [0]
    base = game["is_terminal"]

    def counted(s) -> bool:
        counter[0] += 1
        return base(s)

    game["is_terminal"] = counted
    move, score = fn(state, *args, **game)
    return move, score, counter[0]


# ---------------------------------------------------------------- 评估函数三档

def random_eval(_state: Board) -> float:
    """「坏」评估：不看局面，返回随机分——等于没有评估函数。"""
    return random.uniform(-1, 1)


def material_only(state: Board) -> float:
    """「弱」评估：只看子力差（谁占格子多），完全不看连线威胁。"""
    w = state.winner()
    if w != 0:
        return WIN_SCORE * w
    return float(state.cells.count(X_PLAYER) - state.cells.count(O_PLAYER))


CONFIGS = (("坏评估（随机分）", random_eval),
           ("弱评估（只看子力）", material_only),
           ("好评估（连线威胁）", None))       # None = Board.evaluate


def eval_value(ev: Optional[Callable], state: Board) -> float:
    return state.evaluate() if ev is None else ev(state)


# ---------------------------------------------------------------- 实验一：深度的代价

def experiment_depth_cost(size: int = 5, win_len: int = 4, max_depth: int = 6) -> list:
    """搜得越深，访问节点数涨得多快——先看清"深度是要花钱的"。"""
    Board.configure(size, win_len)
    print(f"== 实验一：搜索深度 vs 访问节点数（{size}×{size} {win_len} 连，空棋盘，剪枝版） ==")
    print(f"{'depth':>6} | {'访问节点':>12} | {'耗时(ms)':>10} | 选中落子")
    print("-" * 52)
    rows = []
    for depth in range(1, max_depth + 1):
        state = Board()
        t0 = time.perf_counter()
        move, score, nodes = count_nodes(
            alphabeta, state, depth, float("-inf"), float("inf"), True, **interface())
        ms = (time.perf_counter() - t0) * 1000
        rows.append((depth, nodes, ms, move))
        print(f"{depth:>6} | {nodes:>12,} | {ms:>10.1f} | {move}")
    return rows


# ---------------------------------------------------------------- 自对弈

def play_match(size: int, win_len: int, cfg_a: tuple, cfg_b: tuple, games: int,
               rng: random.Random) -> dict:
    """让配置 A 与 B 各下 `games` 局，**每局交换先后手**，并分别统计先后手战绩。

    cfg = (评估函数 or None, 深度)。分开统计先手/后手是必要的：连珠类游戏先手优势极大，
    混在一起会把"先手赢"误读成"配置更强"。
    """
    Board.configure(size, win_len)
    ev_a, depth_a = cfg_a
    ev_b, depth_b = cfg_b
    res = dict(a_win=0, b_win=0, draw=0, a_first_win=0, a_second_win=0)

    for g in range(games):
        a_is_first = (g % 2 == 0)
        state = Board()
        while not state.is_terminal():
            first = state.player == X_PLAYER
            use_a = first if a_is_first else not first
            ev = ev_a if use_a else ev_b
            depth = depth_a if use_a else depth_b
            game = interface(evaluate=lambda s, e=ev: eval_value(e, s))
            move, _ = alphabeta(state, depth, float("-inf"), float("inf"),
                                state.player == X_PLAYER, **game)
            if move is None:                       # 理论上不会发生；防御性兜底
                move = rng.choice(state.get_moves())
            state = state.apply(move)

        w = state.winner()
        if w == 0:
            res["draw"] += 1
        elif (w == X_PLAYER) == a_is_first:
            res["a_win"] += 1
            res["a_first_win" if a_is_first else "a_second_win"] += 1
        else:
            res["b_win"] += 1
    return res


# ---------------------------------------------------------------- 实验二：评估质量

def experiment_eval_quality(games: int = 6, size: int = 4, win_len: int = 3) -> None:
    """同搜索、同深度，只换评估函数：与「好评估」对打，谁赢得多？

    用 4×4 三连：棋盘小、容易分胜负，能把"评估"这一项的差异单独放大出来。
    """
    print(f"\n== 实验二：评估质量决定棋力（{size}×{size} {win_len} 连，"
          f"同深度 depth=2，各 {games} 局交换先手） ==")
    rng = random.Random(42)
    print(f"{'配置（评估函数）':<22} | {'胜':>3} | {'负':>3} | {'和':>3} | {'执先手胜':>8}")
    print("-" * 58)
    for name, ev in CONFIGS:
        r = play_match(size, win_len, (ev, 2), (None, 2), games, rng)
        print(f"{name:<22} | {r['a_win']:>3} | {r['b_win']:>3} | {r['draw']:>3} | "
              f"{r['a_first_win']:>8}")
    print("口径：每行都是「该配置 vs 好评估」，胜负按该配置视角统计；交替先手，先手胜单列")


# ---------------------------------------------------------------- 实验三：深度效应

def experiment_depth_effect(games: int = 6, size: int = 6, win_len: int = 4,
                            pairs=((2, 4), (3, 4), (2, 3))) -> None:
    """固定用「好评估」，只改深度：深的一定赢吗？

    用 6×6 四连：比 4×4 更能容纳深度差异，先手优势也没那么压倒（先手胜单列出来）。
    """
    print(f"\n== 实验三：深度效应（{size}×{size} {win_len} 连，两边同用「好评估」，"
          f"各 {games} 局交换先手） ==")
    rng = random.Random(7)
    print(f"{'深 vs 浅':>10} | {'深胜':>4} | {'浅胜':>4} | {'和':>3} | {'深方执先手胜':>12}")
    print("-" * 62)
    for deep, shallow in pairs:
        r = play_match(size, win_len, (None, deep), (None, shallow), games, rng)
        print(f"{deep:>4} vs {shallow:<4} | {r['a_win']:>4} | {r['b_win']:>4} | "
              f"{r['draw']:>3} | {r['a_first_win']:>12}")


def main() -> None:
    experiment_depth_cost()
    experiment_eval_quality()
    experiment_depth_effect()
    print("\n说明：换棋盘尺寸 / 连珠数 / 评估函数后重跑即可复现全部结论；")
    print("     搜索本体始终是教学目录的 impl.alphabeta——本项目只换了棋类与评估。")


if __name__ == "__main__":
    main()
