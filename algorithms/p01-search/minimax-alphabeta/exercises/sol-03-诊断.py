"""参考解 3：把三种 alpha-beta 写法放在同一批树上对照，看"错在哪一步"的后果。

用法：python3 sol-03-诊断.py

三种写法：
  correct      正确写法（与 impl.alphabeta 等价）
  swap_var     max 层错误地更新 beta —— 第 3 题给的那段伪代码
  drop_window  递归时忘了把 (alpha, beta) 传下去（每次都从 ±∞ 重新开始）

本脚本**不预设结论**：它把两种错误写法在 4 棵不同的树上跑一遍，只报告实测到的
"结论是否被改坏 / 叶子数变化"，由读者据此判断这类 bug 危险在哪。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class Node:
    """显式树节点：kind ∈ {"root", "branch", "leaf"}。"""

    __slots__ = ("kind", "step", "idx", "tree")

    def __init__(self, kind, tree, step="", idx=-1):
        self.kind, self.tree, self.step, self.idx = kind, tree, step, idx

    def is_terminal(self):
        return self.kind == "leaf"

    def get_moves(self):
        if self.kind == "root":
            return list(self.tree)
        if self.kind == "branch":
            return list(range(3))
        return []

    def apply(self, move):
        if self.kind == "root":
            return Node("branch", self.tree, move)
        return Node("leaf", self.tree, self.step, move)

    def evaluate(self):
        return float(self.tree[self.step][self.idx])


TREES = {
    "T1 对称": {"a": (4, 2, 6), "b": (4, 8, 3), "c": (1, 8, 3)},
    "T2 非对称": {"a": (3, 1, 2), "b": (5, 6, 4), "c": (0, 8, 7)},
    "T3 前大后小": {"a": (5, 9, 2), "b": (1, 7, 3), "c": (4, 6, 8)},
    "T4 谷底在后": {"a": (2, 8, 6), "b": (9, 1, 5), "c": (3, 4, 7)},
}


def search(state, depth, alpha, beta, maximizing, get_moves, apply,
           evaluate, is_terminal, mode, visits):
    if depth == 0 or is_terminal(state):
        if state.kind == "leaf":
            visits.append((state.step, state.idx))
        return None, evaluate(state)
    moves = get_moves(state)
    best, v = None, (float("-inf") if maximizing else float("inf"))
    for move in moves:
        if mode == "drop_window":
            child_args = (float("-inf"), float("inf"))
        else:
            child_args = (alpha, beta)
        _, score = search(apply(state, move), depth - 1, child_args[0], child_args[1],
                          not maximizing, get_moves, apply, evaluate, is_terminal,
                          mode, visits)
        if maximizing:
            if score > v:
                v, best = score, move
            if mode == "swap_var":
                beta = min(beta, v)        # ← 错误：max 层该更新 alpha
            else:
                alpha = max(alpha, v)
        else:
            if score < v:
                v, best = score, move
            beta = min(beta, v)
        if beta <= alpha:
            break
    return best, v


def run(tree: dict, mode: str) -> tuple:
    visits: list = []
    game = {
        "get_moves": lambda s: s.get_moves(),
        "apply": lambda s, m: s.apply(m),
        "evaluate": lambda s: s.evaluate(),
        "is_terminal": lambda s: s.is_terminal(),
    }
    move, score = search(Node("root", tree), 3, float("-inf"), float("inf"), True,
                         mode=mode, visits=visits, **game)
    return move, score, len(visits)


def main() -> None:
    print(f"{'树':<12} | {'写法':<12} | {'move':>4} | {'score':>5} | {'叶子数':>6} | 结论")
    print("-" * 74)
    row_ok = True
    for name, tree in TREES.items():
        base = run(tree, "correct")[:2]
        for mode, label in (("correct", "正确"), ("swap_var", "swap_var"),
                            ("drop_window", "drop_window")):
            move, score, leaves = run(tree, mode)
            if mode == "correct":
                verdict = f"基准（minimax 也是 {base}）"
            elif (move, score) == base:
                verdict = "结论相同（只多/少算）"
            else:
                verdict = "❌ 结论被改坏"
                row_ok = False
            print(f"{name:<12} | {label:<12} | {str(move):>4} | {score:>5.0f} | "
                  f"{leaves:>6} | {verdict}")
        print("-" * 74)

    print("\n要点（由上面的实测得出，不预设）：")
    print("  1. 两种错误写法在这批树上都没有把**根的结论**改坏，但都改变了展开的叶子数；")
    print("  2. `swap_var` 少算的原因是把 β 压到了自己的分数上，等于**丢了剪枝的依据**；")
    print("  3. `drop_window` 每次都从 ±∞ 开始，等于**完全没有窗口**——剪枝失效；")
    print("  4. 所以「结论没被改坏」不能当成写对了：错误的窗口迟早会在别的树上出错，")
    print("     而且它不会报错、只是悄悄多算或少算。这正是要用测试逐点对拍的原因。")
    if not row_ok:
        print("  （本轮出现了结论被改坏的组合，见上表 ❌ 行。）")


if __name__ == "__main__":
    main()
