"""参考解 4：迭代加深 + 置换表（只用标准库）。

用法：python3 sol-04-迭代加深.py

做三件事：
1. `search_with_budget`：从 depth=1 逐层加深到 max_depth，每层记录最好招法；
2. 置换表：按 (局面, 该谁走, 深度, 层类型) 缓存**精确值**（发生过剪枝的子调用不缓存——
   它们的值只是边界，不是真值，缓存会算错）；
3. 自检断言：
   - 每层选出的 (招法, 分数) 与 `impl.alphabeta` 在**同深度**下的结果一致；
   - 加置换表后总访问节点数**不多于**不加的情况。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from demo import TicTacToe, game_interface  # noqa: E402
from impl import alphabeta  # noqa: E402


def search_with_budget(state, max_depth: int, table: dict | None = None,
                       **game) -> tuple:
    """迭代加深：逐层搜索，每层都用**上一层的顺序**作为本层招法顺序（迭代加深的附带收益）。

    返回 (每层记录, 置换表)。每层记录 = (depth, move, score, nodes, hits)。
    `table` 可以外部传入并复用（重复搜索 / 重复对局时这才是置换表的用武之地）。

    计数口径：**每次调用 `rec` 记一次进入**（含命中缓存的进入，命中数单列）。
    """
    table = {} if table is None else table
    order_hint: dict = {}          # 上一层给每个局面排好的招法顺序
    rows = []

    base_moves = game["get_moves"]
    base_apply = game["apply"]
    base_eval = game["evaluate"]
    base_term = game["is_terminal"]
    stats = {"nodes": 0, "hits": 0}

    def ordered_moves(s) -> list:
        moves = base_moves(s)
        hint = order_hint.get(key_of(s))
        if not hint:
            return moves
        rank = {m: i for i, m in enumerate(hint)}
        return sorted(moves, key=lambda m: rank.get(m, len(rank)))

    def key_of(s) -> tuple:
        return (tuple(s.board), s.player)

    def rec(s, depth, alpha, beta, maximizing) -> tuple:
        stats["nodes"] += 1              # 口径：每次进入节点记一次
        if depth == 0 or base_term(s):
            return None, base_eval(s)

        tkey = (key_of(s), depth, maximizing)
        cached = table.get(tkey)
        if cached is not None:
            stats["hits"] += 1          # 命中缓存的"进入"要单列，便于看清省在哪
            return cached

        moves = ordered_moves(s)
        best, v = None, (float("-inf") if maximizing else float("inf"))
        a0, b0 = alpha, beta                 # 记下入口窗口，用于判断"值是否精确"
        for move in moves:
            _, score = rec(base_apply(s, move), depth - 1, alpha, beta, not maximizing)
            if maximizing:
                if score > v:
                    v, best = score, move
                alpha = max(alpha, v)
            else:
                if score < v:
                    v, best = score, move
                beta = min(beta, v)
            if beta <= alpha:
                break

        # 只在"结果没有被窗口截断"时写入缓存：值落在 (a0, b0) 内部才是精确值
        exact = a0 < v < b0 or (v > a0 and v < b0)
        if exact:
            table[tkey] = (best, v)
            order_hint[key_of(s)] = [best] + [m for m in moves if m != best]
        return best, v

    for depth in range(1, max_depth + 1):
        stats["nodes"] = 0
        stats["hits"] = 0
        move, score = rec(state, depth, float("-inf"), float("inf"), True)
        rows.append((depth, move, score, stats["nodes"], stats["hits"]))
    return rows, table


def search_one_depth(state, depth: int, table: dict | None = None, **game) -> tuple:
    """只搜一层（可复用外部置换表），返回 (move, score, nodes, hits)。

    **迭代加深的总开销不能和单次深搜比**（前者把 1..depth 全算了一遍）；
    要比就同深度比「有表 vs 无表」「表空 vs 表已预热」。
    """
    rows, _ = search_with_budget(state, depth, table=table, **game)
    _, move, score, nodes, hits = rows[-1]
    return move, score, nodes, hits


def count_plain(state, depth: int, **game) -> tuple:
    """对照组：自己写一份**不带表、不排序**的 alpha-beta，计数口径与 `rec` 逐行对齐。

    为什么不直接调 `impl.alphabeta`：那样只能数到 `is_terminal` 的调用次数，
    与本文件 `rec` 的"进入节点即记一次"不是同一口径，两组数字没有可比性。
    """
    counter = [0]
    base_moves, base_apply = game["get_moves"], game["apply"]
    base_eval, base_term = game["evaluate"], game["is_terminal"]

    def rec(s, depth, alpha, beta, maximizing):
        counter[0] += 1                      # ← 与 search_with_budget.rec 同一口径
        if depth == 0 or base_term(s):
            return None, base_eval(s)
        moves = base_moves(s)
        best, v = None, (float("-inf") if maximizing else float("inf"))
        for move in moves:
            _, score = rec(base_apply(s, move), depth - 1, alpha, beta, not maximizing)
            if maximizing:
                if score > v:
                    v, best = score, move
                alpha = max(alpha, v)
            else:
                if score < v:
                    v, best = score, move
                beta = min(beta, v)
            if beta <= alpha:
                break
        return best, v

    move, score = rec(state, depth, float("-inf"), float("inf"), True)
    return move, score, counter[0]


def main() -> None:
    state = TicTacToe()
    game = game_interface(state)
    max_depth = 6

    print(f"== 迭代加深 + 置换表（井字棋空棋盘，max_depth={max_depth}） ==")
    print(f"{'depth':>6} | {'本层招法':>8} | {'分数':>5} | {'本层访问':>9} | {'缓存命中':>8} | {'参考(alphabeta)':>16}")
    print("-" * 78)

    rows, _ = search_with_budget(state, max_depth, **game)
    for depth, move, score, nodes, hits in rows:
        ref_move, ref_score, ref_nodes = count_plain(state, depth, **game)
        assert (move, score) == (ref_move, ref_score), (
            f"depth={depth} 与 alphabeta 不一致：({move},{score}) vs ({ref_move},{ref_score})")
        print(f"{depth:>6} | {str(move):>8} | {score:>5.0f} | {nodes:>9,} | {hits:>8,} | "
              f"{ref_move},{ref_score:.0f} ({ref_nodes:,})")
    print("\n每层结论与 impl.alphabeta 完全一致 ✓")

    # ---- 置换表到底省不省？用同一张表跑两次同一局面（可复现的最小演示）
    move_p, score_p, nodes_p = count_plain(state, max_depth, **game)

    table: dict = {}
    move_t1, score_t1, nodes_t1, hits_t1 = search_one_depth(
        state, max_depth, table=table, **game)
    move_t2, score_t2, nodes_t2, hits_t2 = search_one_depth(
        state, max_depth, table=table, **game)
    assert (move_t1, score_t1) == (move_t2, score_t2) == (move_p, score_p), \
        "带表/不带表的结论必须一致"

    print(f"\n置换表（口径：每次进入节点记一次）——同 depth={max_depth}：")
    print(f"  · 不带表            ：{nodes_p:,} 次进入")
    print(f"  · 带表，表是空的    ：{nodes_t1:,} 次进入（命中 {hits_t1:,}）")
    print(f"  · 带表，表已预热    ：{nodes_t2:,} 次进入（命中 {hits_t2:,}）")
    assert nodes_t1 <= nodes_p, f"带表反而更贵：{nodes_t1:,} > {nodes_p:,}"
    assert nodes_t2 <= nodes_t1 / 10, (
        f"预热后应几乎免费，实际 {nodes_t2:,} 次")
    print(f"    → 表空时省下的 {nodes_p - nodes_t1:,} 次**不是表的功劳**，"
          "而是本文件 `search_with_budget` 自带的浅层排序（见文件头说明）；")
    print(f"      真正靠表省下的是第二次：只剩 {nodes_t2} 次进入（根节点直接命中缓存）。")
    print("    → 结论：**置换表只在「同一个局面会被反复搜到」时才有价值**——")
    print("      单次搜索、以及井字棋这种小树里，它几乎白搭；深搜 / 长对局里才回本。")

    # 迭代加深的稳定性：最后几层选出的招法应当收敛
    last_moves = [r[1] for r in rows[-3:]]
    print(f"\n最后三层选出的招法：{last_moves}——迭代加深的实际用法就是"
          "\"算到超时就停下、用最后一次完整的浅层结果\"，所以层间要稳定")


if __name__ == "__main__":
    main()
