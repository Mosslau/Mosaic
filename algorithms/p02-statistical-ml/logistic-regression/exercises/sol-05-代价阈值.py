"""参考解：第 5 题（迁移）——按业务代价选阈值

    uv run python sol-05-代价阈值.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import Model, confusion, roc_auc  # noqa: E402


def cost_at(y_true, proba, threshold, c_fn, c_fp):
    pred = (proba >= threshold).astype(int)
    tp, fp, fn, tn = confusion(y_true, pred)
    return c_fn * fn + c_fp * fp, tp, fp, fn, tn


def best_threshold(y_true, proba, c_fn, c_fp, grid=np.linspace(0.01, 0.95, 95)):
    rows = [(t, *cost_at(y_true, proba, t, c_fn, c_fp)) for t in grid]
    best = min(rows, key=lambda r: r[1])
    return best, rows


def main() -> None:
    X, y = D.make_imbalanced(n=4000)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0,
                                              stratify=y)
    model = Model(lr=0.5, epochs=8000, tol=1e-12).fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)
    print(f"测试集：{len(y_te)} 个样本，正类 {y_te.mean():.1%}，AUC {roc_auc(y_te, proba):.4f}")

    for c_fn, c_fp in ((20, 1), (2, 1)):
        (best_t, best_cost, tp, fp, fn, tn), rows = best_threshold(y_te, proba, c_fn, c_fp)
        default_cost, *_ = cost_at(y_te, proba, 0.5, c_fn, c_fp)
        print(f"\n代价比 FN:FP = {c_fn}:{c_fp}")
        print(f"{'阈值':>6} | {'TP':>4} | {'FP':>4} | {'FN':>4} | {'总代价':>7}")
        print("-" * 38)
        for t in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6):
            c, tp_, fp_, fn_, _ = cost_at(y_te, proba, t, c_fn, c_fp)
            print(f"{t:6.1f} | {tp_:4d} | {fp_:4d} | {fn_:4d} | {c:7d}")
        print(f"→ 最优阈值 {best_t:.2f}，代价 {best_cost}（默认 0.5 是 {default_cost}）")
        if c_fn == 20:
            assert best_t < 0.5, "漏判更贵时，最优阈值应低于 0.5"
            assert best_cost < default_cost, "调阈值应降低总代价"
            t20 = best_t
        else:
            assert best_t > t20, "漏判变便宜后，阈值应右移"

    print("\n→ 阈值不是模型参数，而是业务代价的函数。")


if __name__ == "__main__":
    main()
