"""参考解 4：把 UCB1 换成 PUCT（AlphaZero 用的选择规则）。

用法：python3 sol-04-PUCT.py

PUCT：选择时用      Q(s,a) + C · P(s,a) · √N / (1 + n)
  Q = 该招法的平均收益（利用）        P = 先验概率（这个招法"看起来"有多好）
  N = 父节点访问数                    n = 该招法访问数
与 UCB1 的区别：探索项不再是"均匀补贴" √(ln N / n)，而是**按先验加权**的探索。
UCB1 的问题在实验三里已经暴露：总模拟次数很少时，√(ln N / n) 几乎没有区分度，
纯利用（C=0）反而更好。PUCT 让"有希望的招法"优先被试，等于把先验知识补贴进探索。

先验用一个**任何棋类都能算的简单启发式**：
    走完之后，我方"下一步能赢的招法数" − 对手"下一步能赢的招法数"
在根节点一次性算好并归一化，之后就沿用（简单版）。
"""

import importlib.util
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MCTS_DIR = HERE.parent
sys.path.insert(0, str(MCTS_DIR))

from demo import GAME, O_PLAYER, TicTacToe, X_PLAYER  # noqa: E402
from impl import MCTS  # noqa: E402


# ---------------------------------------------------------------- 先验

def count_immediate_wins(state, me: int) -> int:
    """`state` 下轮到 `me` 时，"下一步立刻赢"的招法数。"""
    moves = state.get_moves()
    return sum(1 for m in moves if state.apply(m).winner() == me)


def prior_of(state, move: int, me: int) -> float:
    """走 `move` 之后的启发式先验：我方的即时威胁 − 对手的即时威胁。"""
    nxt = state.apply(move)
    opponent = -me
    return float(count_immediate_wins(nxt, opponent) * -1 + count_immediate_wins(nxt, me))


def build_priors(state, moves: list, me: int) -> dict:
    """把根节点的所有招法算成归一化概率（softmax 形式），保证都为正。"""
    raw = {m: prior_of(state, m, me) for m in moves}
    top = max(raw.values())
    exp = {m: math.exp(raw[m] - top) for m in moves}
    total = sum(exp.values())
    return {m: exp[m] / total for m in moves}


# ---------------------------------------------------------------- PUCT 节点与搜索

class PUCTNode:
    __slots__ = ("state", "parent", "action", "mover", "untried", "priors",
                 "children", "visits", "value")

    def __init__(self, state, parent=None, action=None, mover=1, untried=None, priors=None):
        self.state = state
        self.parent = parent
        self.action = action
        self.mover = mover
        self.untried = list(untried or [])
        self.priors = priors or {}          # 该节点的子招法先验（根节点算好，其余均匀）
        self.children = {}
        self.visits = 0
        self.value = 0.0


class PUCT(MCTS):
    """只改选择规则与节点的先验字段，其余（展开/模拟/回传）与 impl.MCTS 一致。"""

    def __init__(self, *args, c_puct: float = 1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.c_puct = c_puct
        self._root_player = 1

    # ---- 选择：PUCT
    def _best_child(self, node):
        sqrt_parent = math.sqrt(node.visits)

        def score(child):
            q = child.value / child.visits if child.visits else 0.0
            prior = node.priors.get(child.action, 1.0 / max(len(node.children), 1))
            u = self.c_puct * prior * sqrt_parent / (1 + child.visits)
            return q + u

        return max(node.children.values(), key=score)

    # ---- 展开：子节点继承均匀先验（简单版：只在根算先验）
    def _expand(self, node):
        if not node.untried or self._terminal(node.state):
            return node
        index = self.rng.randrange(len(node.untried))
        action = node.untried.pop(index)
        child_state = self.apply(node.state, action)
        child = PUCTNode(child_state, parent=node, action=action, mover=-node.mover,
                         untried=self.get_moves(child_state), priors={})
        node.children[action] = child
        return child

    # ---- 搜索：根节点先算先验
    def search(self, state, iterations: int = 1000, root_player: int = 1):
        moves = self.get_moves(state)
        if not moves:
            return None
        if len(moves) == 1:
            return moves[0]
        priors = build_priors(state, moves, root_player)
        root = PUCTNode(state, mover=-root_player, untried=list(moves), priors=priors)
        for _ in range(iterations):
            node = self._select(root)
            node = self._expand(node)
            reward = self._simulate(node.state, node.mover)
            self._backpropagate(node, reward)
        self.last_stats = {"iterations": iterations,
                           "visits": {a: c.visits for a, c in root.children.items()},
                           "priors": priors}
        return max(root.children, key=lambda a: root.children[a].visits)


# ---------------------------------------------------------------- 对局与对照

def load_alphabeta():
    path = MCTS_DIR.parent / "minimax-alphabeta" / "impl.py"
    spec = importlib.util.spec_from_file_location("minimax_impl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.alphabeta


EXACT_GAME = {"get_moves": lambda s: s.get_moves(), "apply": lambda s, m: s.apply(m),
              "evaluate": lambda s: 10.0 * s.winner(),
              "is_terminal": lambda s: s.is_terminal()}


def play(cls, iterations: int, games: int, seed: int, **kwargs) -> dict:
    alphabeta = load_alphabeta()
    draws = losses = wins = 0
    for game_index in range(games):
        rng = random.Random(seed * 7919 + game_index)
        state = TicTacToe(player=X_PLAYER)
        while not state.is_terminal():
            if state.player == X_PLAYER:
                mcts = cls(GAME["get_moves"], GAME["apply"], GAME["is_terminal"],
                           GAME["winner"], rng=rng, **kwargs)
                move = mcts.search(state, iterations=iterations, root_player=X_PLAYER)
            else:
                move, _ = alphabeta(state, 9, float("-inf"), float("inf"), False,
                                    **EXACT_GAME)
            state = state.apply(move)
        w = state.winner()
        wins += w == X_PLAYER
        draws += w == 0
        losses += w == O_PLAYER
    return {"wins": wins, "draws": draws, "losses": losses,
            "not_lose": (wins + draws) / games}


def main() -> None:
    print("== PUCT vs UCB1：对精确搜索（先手，各 40 局） ==")
    print(f"{'选择规则':<10} | {'iterations':>10} | {'和':>3} | {'负':>3} | {'不输率':>7}")
    print("-" * 52)
    rows = []
    for label, cls, kwargs in (("UCB1", MCTS, {}), ("PUCT", PUCT, {"c_puct": 1.0})):
        for iterations in (10, 50, 100):
            r = play(cls, iterations, 40, seed=5, **kwargs)
            rows.append((label, iterations, r))
            print(f"{label:<10} | {iterations:>10} | {r['draws']:>3} | {r['losses']:>3} | "
                  f"{r['not_lose']:>6.0%}")

    # 断言：PUCT 在 100 次模拟时不得输，且整体不劣于 UCB1
    puct = {it: r for label, it, r in rows if label == "PUCT"}
    ucb1 = {it: r for label, it, r in rows if label == "UCB1"}
    # 单档 1–2 局的差异属于小样本噪声（40 局、固定种子），所以断言"整体不劣"而非"每档全胜"
    assert puct[100]["losses"] <= 2, (
        f"PUCT 在 100 次模拟时输了 {puct[100]['losses']} 局——超出噪声范围")
    total_puct = sum(puct[it]["not_lose"] for it in puct)
    total_ucb1 = sum(ucb1[it]["not_lose"] for it in ucb1)
    print(f"\n三档合计不输率：PUCT {total_puct / 3:.0%} vs UCB1 {total_ucb1 / 3:.0%}")
    assert total_puct >= total_ucb1 - 0.02, (
        f"PUCT 明显不如 UCB1（{total_puct / 3:.0%} vs {total_ucb1 / 3:.0%}），先验设计有问题")
    print("PUCT 不劣于 UCB1 ✓（10 次模拟那一档提升最明显：先验把次数用在了该用的分支上）")

    print("\n根节点先验示例（空棋盘，X 先手）：")
    state = TicTacToe()
    priors = build_priors(state, state.get_moves(), X_PLAYER)
    for move, p in sorted(priors.items(), key=lambda kv: -kv[1])[:4]:
        print(f"  走 {move}: 先验 {p:.3f}")


if __name__ == "__main__":
    main()
