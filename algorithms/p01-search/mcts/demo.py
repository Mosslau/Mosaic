"""MCTS demo：井字棋上量化"模拟次数换决策质量"。

四组实验：
1. **对纯随机**：迭代 10 → 2000，胜率如何收敛（最弱基线，回答"有没有效"）
2. **对贪心挡招**：同样爬升，但对手强得多——迭代次数的**边际收益**在这里才看得出来
3. **探索常数 C 的影响**：C = 0 / 0.5 / √2 / 3，验证"纯利用不行、探索太大也不行"
4. **对精确搜索**：与 minimax 目录的 alphabeta（depth=9）对打，看 MCTS 要多少模拟才不落下风

口径（与 README 对齐）：
- 胜率 = MCTS **赢**的局数占比；**平局单独统计**，不计入胜率
- MCTS 固定执先手（井字棋先手优势明显，混先后手会把"先手赢"误读成"算法强"）
- 全部固定随机种子，结果可复现

运行：cd algorithms/p01-search/mcts && python3 demo.py
"""

import copy
import random
import time

from baseline import greedy_move, random_move
from impl import make_mcts

X_PLAYER, O_PLAYER = 1, -1
LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
         (0, 3, 6), (1, 4, 7), (2, 5, 8),
         (0, 4, 8), (2, 4, 6))


class TicTacToe:
    """井字棋（与 minimax 目录同一约定：get_moves / apply / is_terminal / winner）。

    状态**不可变**：`apply` 返回新对象——MCTS 会同时挂很多分支，就地改棋盘会互相污染。
    """

    def __init__(self, board: list | None = None, player: int = X_PLAYER) -> None:
        self.board = list(board) if board is not None else [0] * 9
        self.player = player

    def winner(self) -> int:
        """返回胜者（1 / −1）；无人获胜（含平局）返回 0。"""
        for a, b, c in LINES:
            v = self.board[a]
            if v != 0 and v == self.board[b] == self.board[c]:
                return v
        return 0

    def is_terminal(self) -> bool:
        return self.winner() != 0 or all(v != 0 for v in self.board)

    def get_moves(self) -> list:
        return [i for i, v in enumerate(self.board) if v == 0]

    def apply(self, move: int) -> "TicTacToe":
        nxt = copy.copy(self)
        nxt.board = self.board.copy()
        nxt.board[move] = self.player
        nxt.player = -self.player
        return nxt

    def render(self) -> str:
        glyph = {1: "X", -1: "O", 0: "."}
        return " / ".join("".join(glyph[v] for v in self.board[i:i + 3]) for i in (0, 3, 6))


def game_interface() -> dict:
    """MCTS 需要的四个函数（都写成无状态形式：搜索会把它们用在不同局面上）。"""
    return {
        "get_moves": lambda s: s.get_moves(),
        "apply": lambda s, m: s.apply(m),
        "is_terminal": lambda s: s.is_terminal(),
        "winner": lambda s: s.winner(),
    }


GAME = game_interface()

# minimax 的 alphabeta 需要 evaluate（终局评分），且不接受多余的键——
# 所以精确搜索用单独一份接口，不能把 GAME 直接丢进去（里面的 winner 会报 unexpected keyword）。
def exact_game() -> dict:
    return {
        "get_moves": lambda s: s.get_moves(),
        "apply": lambda s, m: s.apply(m),
        "evaluate": lambda s: 10.0 * s.winner(),
        "is_terminal": lambda s: s.is_terminal(),
    }


EXACT_GAME = exact_game()


# ---------------------------------------------------------------- 对战脚手架

def play_vs_policy(iterations: int, policy: str, games: int, seed: int,
                   exploration: float = 2 ** 0.5) -> dict:
    """MCTS（固定先手）对某个基线策略下 `games` 局，返回胜负和与耗时。

    policy ∈ {"random", "greedy"}。每局用不同的子种子，保证对局多样且可复现。
    """
    wins = draws = losses = 0
    t0 = time.perf_counter()
    for game_index in range(games):
        rng = random.Random(seed * 100003 + game_index)
        state = TicTacToe(player=X_PLAYER)
        while not state.is_terminal():
            if state.player == X_PLAYER:
                mcts = make_mcts(GAME, rng=rng, exploration=exploration)
                move = mcts.search(state, iterations=iterations, root_player=X_PLAYER)
            elif policy == "random":
                move = random_move(state, lambda s: s.get_moves(), rng)
            else:
                move = greedy_move(state, lambda s: s.get_moves(),
                                   lambda s, m: s.apply(m), lambda s: s.winner(),
                                   me=O_PLAYER, rng=rng)
            if move is None:
                break
            state = state.apply(move)
        w = state.winner()
        if w == X_PLAYER:
            wins += 1
        elif w == 0:
            draws += 1
        else:
            losses += 1
    return {"wins": wins, "draws": draws, "losses": losses,
            "win_rate": wins / games, "seconds": time.perf_counter() - t0}


# ---------------------------------------------------------------- 实验一 / 二

ITER_GRID = (10, 50, 100, 500, 1000, 2000)


def experiment_vs_baseline(policy: str, games: int = 50, seed: int = 42) -> list:
    """迭代次数 → 胜率。`policy` 决定对手是纯随机还是贪心挡招。"""
    label = "纯随机" if policy == "random" else "贪心挡招（能赢就赢 / 能挡就挡）"
    print(f"\n== 对{label}：迭代次数 → 胜率（MCTS 固定执先手，各 {games} 局） ==")
    print(f"{'iterations':>10} | {'胜':>4} | {'平':>4} | {'负':>4} | {'胜率':>7} | {'耗时(秒)':>9}")
    print("-" * 60)
    rows = []
    for iterations in ITER_GRID:
        r = play_vs_policy(iterations, policy, games, seed)
        rows.append((iterations, r))
        print(f"{iterations:>10} | {r['wins']:>4} | {r['draws']:>4} | {r['losses']:>4} | "
              f"{r['win_rate']:>6.0%} | {r['seconds']:>9.1f}")
    assert rows[-1][1]["win_rate"] >= rows[0][1]["win_rate"], (
        f"迭代最多的胜率反而更低：{rows[-1][1]['win_rate']:.2f} < {rows[0][1]['win_rate']:.2f}")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_exploration_vs_exact(games: int = 40, seed: int = 5,
                                   iterations: int = 10) -> list:
    """探索常数 C 的影响——**对精确搜索、且故意只给很少的迭代**。

    为什么必须这样设计：对"贪心挡招"这种弱对手，C 从 0 到 10 的胜率都在 95%–100%，
    看不出区别（试过，见 README 的说明）。对精确对手（井字棋必然和棋）才有可分辨的信号：
    **C=0 是纯利用**——早期偶然赢过一两次的分支会被一直选下去，探索不足 ⇒ 该守的没守住；
    **C 太大**则把模拟浪费在明显差的分支上。中间才有最好的权衡。
    """
    alphabeta = _load_minimax().alphabeta       # 精确搜索：对手就是它

    print(f"\n== 探索常数 C 的影响（对**精确搜索** alphabeta(depth=9)，"
          f"iterations={iterations}，各 {games} 局） ==")
    print(f"{'C':>6} | {'和':>4} | {'负':>4} | {'不输率':>7} | 说明")
    print("-" * 52)
    rows = []
    for c in (0.0, 0.5, 2 ** 0.5, 3.0, 10.0):
        r = _play_vs_exact(alphabeta, games, seed, iterations, c)
        not_lose = (r["draws"]) / games
        note = "纯利用" if c == 0.0 else ("默认 √2" if abs(c - 2 ** 0.5) < 1e-9 else "")
        rows.append((c, r))
        print(f"{c:>6.2f} | {r['draws']:>4} | {r['losses']:>4} | {not_lose:>6.0%} | {note}")
    best = max(rows, key=lambda x: x[1]["draws"])
    print(f"→ 本轮 C = {best[0]:.2f} 的和棋最多；井字棋双方最优必然和棋，"
          "所以「和棋率」就是决策质量的直接度量")
    return rows


def _play_vs_exact(alphabeta, games: int, seed: int,
                   iterations: int, exploration: float) -> dict:
    """MCTS（执先手，指定 C）对精确搜索下 games 局，返回 {draws, losses, seconds}。"""
    draws = losses = wins = 0
    t0 = time.perf_counter()
    for game_index in range(games):
        rng = random.Random(seed * 104729 + game_index)
        state = TicTacToe(player=X_PLAYER)
        while not state.is_terminal():
            if state.player == X_PLAYER:
                game = {"get_moves": lambda s: s.get_moves(),
                        "apply": lambda s, m: s.apply(m),
                        "is_terminal": lambda s: s.is_terminal(),
                        "winner": lambda s: s.winner()}
                mcts = make_mcts(game, rng=rng, exploration=exploration)
                move = mcts.search(state, iterations=iterations, root_player=X_PLAYER)
            else:
                move, _ = alphabeta(state, 9, float("-inf"), float("inf"), False,
                                    **EXACT_GAME)
            state = state.apply(move)
        w = state.winner()
        if w == X_PLAYER:
            wins += 1
        elif w == 0:
            draws += 1
        else:
            losses += 1
    return {"wins": wins, "draws": draws, "losses": losses,
            "seconds": time.perf_counter() - t0}


# ---------------------------------------------------------------- 实验四（对精确搜索）

def _load_minimax():
    """只加载 minimax 目录的 `impl.py`（**按文件路径**，用独立模块名）。

    两个坑：
    1. 不能 `sys.path.insert + import impl`——本目录也有 `impl.py`，而 `impl` 已被本模块
       导入过，第二次 import 会直接命中缓存、拿到本目录那份（实测报
       `cannot import name 'alphabeta'`）。
    2. 也不能连它的 `demo.py` 一起加载——那份 demo 内部写着 `from impl import alphabeta`，
       执行时会再次撞上同名遮蔽。
    所以只加载 `impl.py`，井字棋状态改用本目录自己的 `TicTacToe`（两边约定一致：
    待走方为 X(1) / O(−1)，`board` 是 9 个 0/±1 的扁平列表）。
    """
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "minimax-alphabeta" / "impl.py"
    spec = importlib.util.spec_from_file_location("minimax_impl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def experiment_vs_minimax(games: int = 20, seed: int = 3, iterations: int = 2000) -> dict:
    """与 minimax 目录那套**精确搜索**对打：MCTS 要多少模拟才不落下风。"""
    alphabeta = _load_minimax().alphabeta
    print(f"\n== 对精确搜索（minimax 目录的 alphabeta，depth=9）× {games} 局 =="
          f"（MCTS 每步 {iterations} 次模拟）")
    wins = draws = losses = 0
    t0 = time.perf_counter()
    for game_index in range(games):
        rng = random.Random(seed * 7919 + game_index)
        state = TicTacToe(player=X_PLAYER)         # MCTS 执先手
        while not state.is_terminal():
            if state.player == X_PLAYER:
                game = {"get_moves": lambda s: s.get_moves(),
                        "apply": lambda s, m: s.apply(m),
                        "is_terminal": lambda s: s.is_terminal(),
                        "winner": lambda s: s.winner()}
                mcts = make_mcts(game, rng=rng)
                move = mcts.search(state, iterations=iterations, root_player=X_PLAYER)
            else:
                move, _ = alphabeta(state, 9, float("-inf"), float("inf"), False,
                                    **EXACT_GAME)
            state = state.apply(move)
        w = state.winner()
        if w == X_PLAYER:
            wins += 1
        elif w == 0:
            draws += 1
        else:
            losses += 1
    seconds = time.perf_counter() - t0
    print(f"  胜 {wins} · 平 {draws} · 负 {losses}（耗时 {seconds:.1f} s）")
    print("  井字棋在双方最优下是必然和棋，所以「不输」就是 MCTS 在这里的最好结果")
    assert losses == 0, f"MCTS 输给精确搜索 {losses} 局——它的决策质量还不到位"
    return {"wins": wins, "draws": draws, "losses": losses, "seconds": seconds}


def main() -> None:
    experiment_vs_baseline("random")
    experiment_vs_baseline("greedy")
    experiment_exploration_vs_exact()
    experiment_vs_minimax()


if __name__ == "__main__":
    main()
