"""参考解 2：把练习里那棵显式树喂给 impl 的两个版本，打印结论与剪枝轨迹。

用法：python3 sol-02-手算.py
只用标准库；不依赖 demo.py —— 这棵树是专门为手算练习写的。
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from impl import alphabeta, minimax  # noqa: E402

# 练习第 2 题的树：根（max）三个招法，每个招法下对手（min）三个应对
TREE = {
    "a": (4, 2, 6),
    "b": (4, 8, 3),
    "c": (1, 8, 3),
}
LEAVES = 3


class HandTree:
    """显式小树：一个类担任三种节点，靠 `kind` 区分。

    状态表示
      ("root",)         根，我方 max，招法 = 三个招法名
      ("branch", step)  某招法下的对手层，min，招法 = 三个应对编号
      ("leaf", step, i) 终局评分
    """

    __slots__ = ("kind", "step", "idx")

    def __init__(self, kind: str, step: str = "", idx: int = -1) -> None:
        self.kind, self.step, self.idx = kind, step, idx

    def is_terminal(self) -> bool:
        return self.kind == "leaf"

    def get_moves(self) -> list:
        if self.kind == "root":
            return list(TREE)
        if self.kind == "branch":
            return list(range(LEAVES))
        return []

    def apply(self, move: Any) -> "HandTree":
        if self.kind == "root":
            return HandTree("branch", move)
        return HandTree("leaf", self.step, move)

    def evaluate(self) -> float:
        return float(TREE[self.step][self.idx])


def run(fn, *args) -> tuple:
    """跑一次搜索，返回 (move, score, 访问节点数, 访问过的叶子列表)。"""
    counter, visited = [0], []

    def counted(state: HandTree) -> bool:
        counter[0] += 1
        if state.kind == "leaf":
            visited.append((state.step, state.idx))
        return state.is_terminal()

    game = {
        "get_moves": lambda s: s.get_moves(),
        "apply": lambda s, m: s.apply(m),
        "evaluate": lambda s: s.evaluate(),
        "is_terminal": counted,
    }
    move, score = fn(HandTree("root"), *args, **game)
    return move, score, counter[0], visited


def main() -> None:
    # 这棵树是三层（根 → 对手层 → 叶子），所以 depth 必须给 3 才能搜到叶子
    plain_move, plain_score, plain_nodes, plain_leaves = run(minimax, 3, True)
    ab_move, ab_score, ab_nodes, ab_leaves = run(
        alphabeta, 3, float("-inf"), float("inf"), True)

    print(f"{'':22} | {'选中的招法':>10} | {'分数':>5} | {'展开叶子数':>10}")
    print("-" * 60)
    print(f"{'不剪枝 minimax':22} | {str(plain_move):>10} | {plain_score:>5.0f} | {len(plain_leaves):>10}")
    print(f"{'剪枝 alphabeta':22} | {str(ab_move):>10} | {ab_score:>5.0f} | {len(ab_leaves):>10}")

    assert (plain_move, plain_score) == (ab_move, ab_score), \
        f"两版结论不一致：{plain_move}/{plain_score} vs {ab_move}/{ab_score}"
    print("\n两版结论一致 ✓（剪枝只改算了多少）")

    all_leaves = [(m, r) for m in TREE for r in range(LEAVES)]
    cut = [x for x in all_leaves if x not in ab_leaves]
    print(f"\nalpha-beta 展开的叶子：{ab_leaves}")
    print(f"被剪掉的分支：{cut}")
    assert cut, "没有剪掉任何分支——树或深度设错了"

    print("\n逐个招法的值（与手算表对照）：")
    for move, leaves in TREE.items():
        print(f"  招法 {move}: 应对 = {leaves} → 对手取最小 = {min(leaves)}")
    print(f"  根取最大 = {max(min(v) for v in TREE.values())}")

    print("\n与参考解的 α/β 表核对：")
    print("  a 结束后 α = 2；b 第一应对后 β = 2 ⇒ β ≤ α，剪掉 b 剩余应对；")
    print("  b 结束后 α = 4；c 之前 β(2) ≤ α(4) ⇒ 整支剪掉 c。")


if __name__ == "__main__":
    main()
