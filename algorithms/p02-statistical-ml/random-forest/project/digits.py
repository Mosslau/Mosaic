"""迁移项目：真实 10 分类上的随机森林 —— 手写数字

    uv run python digits.py

数据来自 sklearn 自带的 `load_digits`（1797 个 8×8 手写数字、10 个类别）。
与教学示例（二维 moons）的差别：
1. 真实数据、10 分类；
2. 用 **OOB** 选树数，不额外切验证集；
3. 同时看准确率、OOB 与跨种子稳定性。
"""

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import RandomForest  # noqa: E402


def accuracy(y_true, y_pred) -> float:
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0,
                                              stratify=y)
    print(f"样本 {len(y)}（训练 {len(y_tr)} / 测试 {len(y_te)}），特征 {X.shape[1]} 维，"
          f"类别 {len(np.unique(y))} 个")

    single = RandomForest(n_trees=1, max_features=None, max_depth=12,
                          random_state=0).fit(X_tr, y_tr)

    print("\n树数扫描（OOB 选树数，不用验证集）：")
    print(f"{'n_trees':>7} | {'OOB':>7} | {'测试 acc':>8} | {'耗时(s)':>7}")
    print("-" * 38)
    rows = []
    for n in (10, 25, 50, 100):
        t0 = time.perf_counter()
        model = RandomForest(n_trees=n, max_depth=12, random_state=0).fit(X_tr, y_tr)
        dt = time.perf_counter() - t0
        rows.append({"n": n, "oob": float(model.oob_score_),
                     "test": accuracy(y_te, model.predict(X_te)), "time": dt})
        print(f"{n:7d} | {rows[-1]['oob']:7.4f} | {rows[-1]['test']:8.4f} | {dt:7.2f}")

    best_oob = max(r["oob"] for r in rows)
    chosen = min(r["n"] for r in rows if r["oob"] >= best_oob - 0.005)
    final = RandomForest(n_trees=chosen, max_depth=12, random_state=0).fit(X_tr, y_tr)
    test_acc = accuracy(y_te, final.predict(X_te))
    oob = float(final.oob_score_)
    print(f"\nOOB 最优 {best_oob:.4f}；选中 n_trees={chosen}，"
          f"测试 {test_acc:.4f}，OOB {oob:.4f}")

    # 稳定性：5 个种子，单树 vs 森林
    singles, forests = [], []
    for seed in range(5):
        s = RandomForest(n_trees=1, max_features=None, max_depth=12,
                         random_state=seed).fit(X_tr, y_tr)
        f = RandomForest(n_trees=chosen, max_depth=12, random_state=seed).fit(X_tr, y_tr)
        singles.append(accuracy(y_te, s.predict(X_te)))
        forests.append(accuracy(y_te, f.predict(X_te)))
    print(f"跨种子：单树 {np.mean(singles):.4f} ± {np.std(singles):.4f}；"
          f"森林 {np.mean(forests):.4f} ± {np.std(forests):.4f}")

    imp = final.feature_importances_
    top = np.argsort(-imp)[:5]
    print("重要性前 5 的像素：" + "、".join(f"x{j}({imp[j]:.3f})" for j in top))

    print("\n== 验收 ==")
    checks = [
        ("测试集覆盖 10 个类别", len(set(final.predict(X_te).tolist())) == 10),
        ("森林测试准确率 ≥ 0.92", test_acc >= 0.92),
        ("OOB 与测试差距 ≤ 0.05", abs(oob - test_acc) <= 0.05),
        ("森林不差于单树", test_acc >= accuracy(y_te, single.predict(X_te)) - 0.01),
        ("选中的树数 ≤ 100", chosen <= 100),
        ("森林跨种子标准差 < 单树", np.std(forests) < np.std(singles)),
        ("重要性归一化", abs(float(imp.sum()) - 1.0) < 1e-9),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print(f"\n→ 真实 10 分类：{chosen} 棵树、测试 {test_acc:.3f}、OOB {oob:.3f}；"
          f"OOB 让'选树数'不需要额外验证集。")


if __name__ == "__main__":
    main()
