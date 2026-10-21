"""参考解：第 5 题（迁移）——验证集选 (lr, n_estimators)

    uv run python sol-05-选参.py
"""

import sys
from pathlib import Path

from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import GradientBoostingRegressor  # noqa: E402


def main() -> None:
    X_tr, X_te, y_tr, y_te = D.make_1d()
    X_sub, X_val, y_sub, y_val = train_test_split(X_tr, y_tr, test_size=0.25,
                                                  random_state=0)
    rows = []
    for lr in (0.05, 0.1, 0.2):
        for n in (50, 100, 200):
            model = GradientBoostingRegressor(n_estimators=n, learning_rate=lr,
                                              random_state=0).fit(X_sub, y_sub)
            rows.append({"lr": lr, "n": n, "val": D.mse(y_val, model.predict(X_val)),
                         "test": D.mse(y_te, model.predict(X_te))})

    print(f"{'lr':>5} | {'n':>4} | {'val MSE':>8} | {'test MSE':>9}")
    print("-" * 34)
    for r in rows:
        print(f"{r['lr']:5.2f} | {r['n']:4d} | {r['val']:8.4f} | {r['test']:9.4f}")

    best = min(rows, key=lambda r: r["val"])
    default = next(r for r in rows if r["lr"] == 0.1 and r["n"] == 100)
    print(f"\n选中 lr={best['lr']}, n={best['n']}（val {best['val']:.4f}，"
          f"test {best['test']:.4f}）")
    print(f"默认 lr=0.1, n=100：test {default['test']:.4f}")
    assert best["test"] <= default["test"] + 0.01, "验证集选出的组合不应明显更差"
    print("\n→ lr 与树数强耦合，必须在验证集上一起选。")


if __name__ == "__main__":
    main()
