"""MCTS 的性质测试。

用法（本目录内）：python3 -m pytest test_impl.py -v

覆盖：
- **回传符号**：这是 MCTS 最容易写反的地方——用一棵手工小树直接验"父方收益"的口径
- **必胜 / 必挡**：能一步赢就赢、对手一步赢要挡（决策正确性的底线）
- **不输给随机**：固定种子下，迭代 200 次对随机 20 局不得告负
- **收敛性**：迭代次数越多，对精确搜索（minimax 的 alphabeta）的和棋率越高
- **与精确搜索打平**：迭代 2000 次时，先手对 alphabeta(depth=9) 必须全部和棋
- **边界**：无可走招法返回 None、只剩一个招法直接返回它、终局局面不崩
- **独立参考校验**：另写一份**不复用 impl 的朴素 rollout 估值**，
  在小局面下与 MCTS 的胜率排序对照，避免"实现自己骗自己"
"""

import importlib.util
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo import EXACT_GAME, GAME, O_PLAYER, TicTacToe, X_PLAYER  # noqa: E402
from impl import MCTS, make_mcts  # noqa: E402


def _load_minimax():
    """按路径加载 minimax 的 impl（同 demo：避免同名模块互相遮蔽）。"""
    path = Path(__file__).resolve().parent.parent / "minimax-alphabeta" / "impl.py"
    spec = importlib.util.spec_from_file_location("minimax_impl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- 回传符号（最容易写错）

class ToyTree:
    """两层玩具对局：根轮到 +1，+1 只有一步可走，走完有两种结局。

    用来直接验证"节点 value 的口径"——如果符号翻转写错，这里立刻暴露。
    """

    def __init__(self, outcome: int, stage: int = 0) -> None:
        self.outcome = outcome      # 该终局的赢家（+1 / −1 / 0 平局）
        self.stage = stage          # 0 = 根，1 = 中间，2 = 终局

    def is_terminal(self) -> bool:
        return self.stage == 2

    def get_moves(self) -> list:
        return [] if self.stage == 2 else [0]

    def apply(self, move) -> "ToyTree":
        return ToyTree(self.outcome, self.stage + 1)

    def winner(self) -> int:
        return self.outcome if self.stage == 2 else 0


def toy_interface():
    return {"get_moves": lambda s: s.get_moves(),
            "apply": lambda s, m: s.apply(m),
            "is_terminal": lambda s: s.is_terminal(),
            "winner": lambda s: s.winner()}


@pytest.mark.parametrize("outcome", [1, -1, 0])
def test_backprop_sign(outcome: int) -> None:
    """回传口径：节点 value 是"**走出这一步的那一方**"的收益。

    根（轮到 +1）→ 唯一招法 → 终局（赢家 outcome）。执行一次 search 后，
    根的唯一子节点（mover = +1）的 value 应当是：赢 +1 / 输 −1 / 平 0。
    """
    mcts = MCTS(toy_interface()["get_moves"], toy_interface()["apply"],
                toy_interface()["is_terminal"], toy_interface()["winner"],
                rng=random.Random(0))
    # 直接手动走一遍四步，避免依赖 search 的内部结构
    root = __import__("impl").Node(ToyTree(outcome), mover=-1, untried=[0])
    child = mcts._expand(root)
    reward = mcts._simulate(child.state, child.mover)
    mcts._backpropagate(child, reward)

    expected_child = 1.0 if outcome == 1 else (-1.0 if outcome == -1 else 0.0)
    assert child.value == pytest.approx(expected_child), (
        f"子节点（mover=+1）的收益应为 {expected_child}，实际 {child.value}")
    # 父节点那一方是 +1 的对手，收益取反
    assert root.value == pytest.approx(-expected_child), (
        f"根（mover=−1）的收益应为 {-expected_child}，实际 {root.value}")
    assert child.visits == root.visits == 1


# ---------------------------------------------------------------- 决策正确性

def test_takes_immediate_win() -> None:
    """X 在 0、1 已连两子：必须下 2。"""
    state = TicTacToe([1, 1, 0, 0, -1, 0, -1, 0, 0], player=X_PLAYER)
    mcts = make_mcts(GAME, rng=random.Random(1))
    assert mcts.search(state, iterations=300, root_player=X_PLAYER) == 2


def test_blocks_immediate_loss() -> None:
    """对手 O 在 0、1 已成两子：必须堵 2，否则必输。"""
    state = TicTacToe([-1, -1, 0, 0, 1, 0, 0, 0, 0], player=X_PLAYER)
    mcts = make_mcts(GAME, rng=random.Random(2))
    assert mcts.search(state, iterations=300, root_player=X_PLAYER) == 2


def test_prefers_center_on_empty_board() -> None:
    """空棋盘：MCTS 应当选中路或角，而不是随便挑——这里只断言"选中合法且访问量集中"。"""
    state = TicTacToe()
    mcts = make_mcts(GAME, rng=random.Random(0))
    move = mcts.search(state, iterations=500, root_player=X_PLAYER)
    assert move in state.get_moves()
    visits = mcts.last_stats["visits"]
    assert sum(visits.values()) == 500, "所有模拟都应该落在某个根分支上"
    assert max(visits.values()) >= 2 * min(visits.values()), (
        "访问量几乎没有分化，UCB 的利用项可能失效")


def test_never_loses_to_random() -> None:
    """固定种子下，迭代 200 次的 MCTS 先手对纯随机 20 局不得告负。"""
    losses = 0
    for game_index in range(20):
        rng = random.Random(1000 + game_index)
        state = TicTacToe(player=X_PLAYER)
        while not state.is_terminal():
            if state.player == X_PLAYER:
                move = make_mcts(GAME, rng=rng).search(
                    state, iterations=200, root_player=X_PLAYER)
            else:
                move = rng.choice(state.get_moves())
            state = state.apply(move)
        if state.winner() == O_PLAYER:
            losses += 1
    assert losses == 0, f"对随机输了 {losses} 局"


# ---------------------------------------------------------------- 与精确搜索的收敛

def _play_vs_exact(iterations: int, games: int, seed: int) -> dict:
    alphabeta = _load_minimax().alphabeta
    draws = losses = 0
    for game_index in range(games):
        rng = random.Random(seed * 7919 + game_index)
        state = TicTacToe(player=X_PLAYER)
        while not state.is_terminal():
            if state.player == X_PLAYER:
                move = make_mcts(GAME, rng=rng).search(
                    state, iterations=iterations, root_player=X_PLAYER)
            else:
                move, _ = alphabeta(state, 9, float("-inf"), float("inf"), False,
                                    **EXACT_GAME)
            state = state.apply(move)
        if state.winner() == 0:
            draws += 1
        elif state.winner() == O_PLAYER:
            losses += 1
    return {"draws": draws, "losses": losses}


def test_matches_exact_search_with_enough_iterations() -> None:
    """迭代 2000 次（先手）对 alphabeta(depth=9)：必须全部和棋——井字棋的最优结果是和棋。

    这一条是"迭代次数换决策质量"的硬证据：少给迭代会输，给够就守得住。
    """
    r = _play_vs_exact(iterations=2000, games=6, seed=3)
    assert r["draws"] == 6 and r["losses"] == 0, f"对精确搜索的实际战绩：{r}"


def test_more_iterations_are_better() -> None:
    """迭代越多，和棋率不应更低（同一批种子下）。"""
    few = _play_vs_exact(iterations=10, games=6, seed=11)
    many = _play_vs_exact(iterations=500, games=6, seed=11)
    assert many["draws"] >= few["draws"], (
        f"迭代 500 的和棋数 {many['draws']} 少于迭代 10 的 {few['draws']}")


# ---------------------------------------------------------------- 边界

def test_terminal_and_single_move() -> None:
    """终局局面返回 None；只剩一个招法时直接返回它（不做无谓模拟）。"""
    full = TicTacToe([1, -1, 1, -1, 1, -1, -1, 1, -1], player=X_PLAYER)
    assert full.is_terminal()
    assert make_mcts(GAME, rng=random.Random(0)).search(full, iterations=50) is None

    almost = TicTacToe([1, -1, 1, -1, 1, -1, -1, 1, 0], player=X_PLAYER)
    assert make_mcts(GAME, rng=random.Random(0)).search(
        almost, iterations=50, root_player=X_PLAYER) == 8


def test_exploration_zero_still_works() -> None:
    """C=0（纯利用）不能崩：老实现里 log(visits) 在 visits=1 时会是 0，容易除零。"""
    state = TicTacToe()
    mcts = make_mcts(GAME, rng=random.Random(0), exploration=0.0)
    move = mcts.search(state, iterations=200, root_player=X_PLAYER)
    assert move in state.get_moves()


# ---------------------------------------------------------------- 独立参考校验

def naive_rollout_value(state: TicTacToe, move: int, trials: int, seed: int,
                        root_player: int = X_PLAYER) -> float:
    """独立参考：**不复用 impl** 的最朴素 rollout 估值（走一步后随机打到底，统计净胜率）。

    只用于对照 MCTS 的排序方向：真正的 MCTS 会建树、会 reuse，这里完全不建树。
    """
    rng = random.Random(seed)
    total = 0.0
    for _ in range(trials):
        s = state.apply(move)
        while not s.is_terminal():
            s = s.apply(rng.choice(s.get_moves()))
        w = s.winner()
        total += 0.0 if w == 0 else (1.0 if w == root_player else -1.0)
    return total / trials


def test_agrees_with_naive_rollout_on_clear_position() -> None:
    """在一个"明显有最优招"的局面里，MCTS 的选择应与朴素 rollout 估值的最优一致。"""
    state = TicTacToe([1, 1, 0, 0, -1, 0, -1, 0, 0], player=X_PLAYER)   # 下 2 即胜
    mcts = make_mcts(GAME, rng=random.Random(5))
    chosen = mcts.search(state, iterations=300, root_player=X_PLAYER)
    ref = {m: naive_rollout_value(state, m, trials=400, seed=7) for m in state.get_moves()}
    best_by_rollout = max(ref, key=lambda m: ref[m])
    assert chosen == best_by_rollout == 2, (
        f"MCTS 选 {chosen}，朴素 rollout 选 {best_by_rollout}（估值 {ref}）")
