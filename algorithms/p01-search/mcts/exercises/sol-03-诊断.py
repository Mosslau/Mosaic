"""参考解 3：把"回传不翻转符号"的 bug 与正确实现放在一起实测。

用法：python3 sol-03-诊断.py

两个层面各验一次：
  1. **不变式层面**（不需要对局）：手工构造一个"赢家已定"的小局面，检查根与子节点的
     value 符号关系——正确实现里两者必然相反；
  2. **对局层面**：两个实现分别对精确搜索（minimax 的 alphabeta）下 40 局，
     看和棋 / 负的差距——这个 bug **不报错**，只在战绩上暴露。
"""

import importlib.util
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MCTS_DIR = HERE.parent
sys.path.insert(0, str(MCTS_DIR))

from demo import GAME, O_PLAYER, TicTacToe, X_PLAYER  # noqa: E402
from impl import MCTS  # noqa: E402


def load_alphabeta():
    """按路径加载 minimax 的 impl（避免同名模块遮蔽）。"""
    path = MCTS_DIR.parent / "minimax-alphabeta" / "impl.py"
    spec = importlib.util.spec_from_file_location("minimax_impl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.alphabeta


EXACT_GAME = {
    "get_moves": lambda s: s.get_moves(),
    "apply": lambda s, m: s.apply(m),
    "evaluate": lambda s: 10.0 * s.winner(),
    "is_terminal": lambda s: s.is_terminal(),
}


class FlippedBackprop(MCTS):
    """故意写错：回传时不翻转符号。其余逻辑与 impl.MCTS 完全一致。"""

    def _backpropagate(self, node, reward_for_mover):
        while node is not None:
            node.visits += 1
            node.value += reward_for_mover        # ← 少了符号翻转
            node = node.parent


# ---------------------------------------------------------------- 不变式层面

def check_sign_invariant(cls, label: str) -> None:
    """构造一个必然决出胜负的局面，检查父子节点的 value 符号是否相反。"""
    # 局面：X 已占 0、1（再下 2 就赢），轮到 O 走 —— O 无论怎么走都挡不住两步
    state = TicTacToe([1, 1, 0, 0, -1, 0, 0, 0, 0], player=X_PLAYER)
    mcts = cls(GAME["get_moves"], GAME["apply"], GAME["is_terminal"], GAME["winner"],
               rng=random.Random(0))
    mcts.search(state, iterations=200, root_player=X_PLAYER)

    # 用一个只有一步的对局直接把父子收益摆出来
    class OneMove:
        def __init__(self, stage=0):
            self.stage = stage
        def is_terminal(self):
            return self.stage == 2
        def get_moves(self):
            return [] if self.stage == 2 else [0]
        def apply(self, move):
            return OneMove(self.stage + 1)
        def winner(self):
            return X_PLAYER if self.stage == 2 else 0

    toy = {"get_moves": lambda s: s.get_moves(), "apply": lambda s, m: s.apply(m),
           "is_terminal": lambda s: s.is_terminal(), "winner": lambda s: s.winner()}
    m = cls(toy["get_moves"], toy["apply"], toy["is_terminal"], toy["winner"],
            rng=random.Random(0))
    from impl import Node
    root = Node(OneMove(), mover=-X_PLAYER, untried=[0])
    child = m._expand(root)
    m._backpropagate(child, m._simulate(child.state, child.mover))
    print(f"  {label}: 子节点 value = {child.value:+.1f}（走出这一步的是 X），"
          f"根 value = {root.value:+.1f}")
    if cls is MCTS:
        assert child.value == 1.0 and root.value == -1.0, "正确实现里两者应当相反"
    else:
        assert child.value == 1.0 and root.value == 1.0, "错误实现里两者会同号"


# ---------------------------------------------------------------- 对局层面

def play_vs_exact(cls, iterations: int, games: int, seed: int) -> dict:
    alphabeta = load_alphabeta()
    draws = losses = wins = 0
    for game_index in range(games):
        rng = random.Random(seed * 7919 + game_index)
        state = TicTacToe(player=X_PLAYER)
        while not state.is_terminal():
            if state.player == X_PLAYER:
                mcts = cls(GAME["get_moves"], GAME["apply"], GAME["is_terminal"],
                           GAME["winner"], rng=rng)
                move = mcts.search(state, iterations=iterations, root_player=X_PLAYER)
            else:
                move, _ = alphabeta(state, 9, float("-inf"), float("inf"), False,
                                    **EXACT_GAME)
            state = state.apply(move)
        w = state.winner()
        wins += w == X_PLAYER
        draws += w == 0
        losses += w == O_PLAYER
    return {"wins": wins, "draws": draws, "losses": losses}


def main() -> None:
    print("== 1) 不变式：父子节点的 value 符号关系 ==")
    check_sign_invariant(MCTS, "正确实现")
    check_sign_invariant(FlippedBackprop, "bug 实现 ")
    print("  → 正确实现必须相反；bug 实现同号（这就是它错的地方）")

    print("\n== 2) 对局：对精确搜索 40 局（每步 50 次模拟） ==")
    ok = play_vs_exact(MCTS, iterations=50, games=40, seed=5)
    bad = play_vs_exact(FlippedBackprop, iterations=50, games=40, seed=5)
    print(f"  {'正确实现':<10} 胜 {ok['wins']:>2} · 平 {ok['draws']:>2} · 负 {ok['losses']:>2}")
    print(f"  {'bug 实现':<10} 胜 {bad['wins']:>2} · 平 {bad['draws']:>2} · 负 {bad['losses']:>2}")
    assert ok["losses"] == 0 or ok["losses"] <= 2, f"正确实现不该输这么多：{ok}"
    assert bad["losses"] > ok["losses"] * 5, (
        f"bug 实现应当明显更差，实际 {bad} vs {ok}")

    print("\n结论：")
    print("  · 这个 bug **不报错、不崩溃**，只是让整棵树按反方向选择——")
    print(f"    战绩从「负 {ok['losses']} 局」变成「负 {bad['losses']} 局」（40 局制）。")
    print("  · 所以正确性必须靠**不变式测试**（父子符号相反）+ **固定种子的战绩回归**来守，")
    print("    不能靠「看起来能跑」。")


if __name__ == "__main__":
    main()
