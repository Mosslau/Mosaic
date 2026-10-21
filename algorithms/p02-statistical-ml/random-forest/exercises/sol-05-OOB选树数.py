"""参考解：第 5 题（迁移）——用 OOB 选树数

    uv run python sol-05-OOB选树数.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import RandomForest  # noqa: E402


def main() -> None:
    X_tr, X_te, y_tr, y_te = D.make_moons_data()
    grid = (5, 10, 25, 50, 100, 200)
    rows = []
    for n in grid:
        model = RandomForest(n_trees=n, random_state=0).fit(X_tr, y_tr)
        rows.append((n, float(model.oob_score_), D.accuracy(y_te, model.predict(X_te))))

    best = max(r[1] for r in rows)
    chosen = min(r[0] for r in rows if r[1] >= best - 0.005)
    chosen_test = next(r[2] for r in rows if r[0] == chosen)
    full_test = rows[-1][2]

    print(f"{'n_trees':>7} | {'OOB':>7} | {'测试 acc':>8}")
    print("-" * 28)
    for n, oob, test in rows:
        mark = " ← 选中" if n == chosen else ""
        print(f"{n:7d} | {oob:7.4f} | {test:8.4f}{mark}")

    print(f"\nOOB 最大值 {best:.4f}；选中 n_trees={chosen}（测试 {chosen_test:.4f}）")
    print(f"200 棵的测试 {full_test:.4f}，差距 {abs(full_test - chosen_test):.4f}")
    assert chosen <= 100, "应在 100 棵内达到饱和"
    assert abs(full_test - chosen_test) <= 0.03, "提前停的测试精度不应明显更差"
    print("\n→ OOB 饱和后继续加树收益很小：选'够用就好'的树数。")


if __name__ == "__main__":
    main()
