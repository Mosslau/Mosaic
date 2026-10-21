"""迁移项目：真实三分类数据上的决策树 —— 葡萄酒产地

    uv run python wine.py

数据来自 sklearn 自带的 `load_wine`（178 个样本、13 维化学特征、3 个产地类别）。
与教学示例的差别：
1. 真实数据、三分类（树天然支持多分类）；
2. 深度、criterion、ccp_alpha 三个旋钮都要用训练集内的 CV 选；
3. 除了准确率，还要量化"树的不稳定性"（bootstrap 预测分歧）。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_wine
from sklearn.model_selection import KFold, train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import framework  # noqa: E402
from impl import DecisionTree  # noqa: E402


def accuracy(y_true, y_pred) -> float:
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def cv_accuracy(make_model, X, y, k: int = 5) -> float:
    scores = []
    for train, val in KFold(n_splits=k, shuffle=True, random_state=0).split(X):
        model = make_model().fit(X[train], y[train])
        scores.append(accuracy(y[val], model.predict(X[val])))
    return float(np.mean(scores))


def main() -> None:
    X, y = load_wine(return_X_y=True)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
    print(f"样本 {len(y)}（训练 {len(y_tr)} / 测试 {len(y_te)}），特征 {X.shape[1]} 维，"
          f"类别 {len(np.unique(y))} 个")

    print("\n深度扫描（5 折 CV，只看训练集）：")
    print(f"{'depth':>5} | {'CV acc':>7}")
    print("-" * 16)
    depth_rows = []
    for depth in range(1, 9):
        cv = cv_accuracy(lambda d=depth: DecisionTree(max_depth=d), X_tr, y_tr)
        depth_rows.append({"depth": depth, "cv": cv})
        print(f"{depth:5d} | {cv:7.4f}")
    best_depth = max(depth_rows, key=lambda r: r["cv"])["depth"]

    print("\ncriterion（在最优深度上）：")
    crit_rows = []
    for criterion in ("gini", "entropy"):
        cv = cv_accuracy(lambda c=criterion: DecisionTree(criterion=c, max_depth=best_depth),
                         X_tr, y_tr)
        crit_rows.append((criterion, cv))
        print(f"  {criterion:8} CV {cv:.4f}")
    best_criterion = max(crit_rows, key=lambda r: r[1])[0]

    path_alphas, _ = framework.pruning_path(X_tr, y_tr)
    picks = np.unique(np.quantile(path_alphas, [0.0, 0.25, 0.5, 0.7, 0.85, 0.95]))
    print("\nccp_alpha 扫描（5 折 CV）：")
    print(f"{'alpha':>8} | {'CV acc':>7}")
    print("-" * 18)
    alpha_rows = []
    for alpha in picks:
        cv = cv_accuracy(lambda a=float(alpha): DecisionTree(max_depth=best_depth, ccp_alpha=a),
                         X_tr, y_tr)
        alpha_rows.append({"alpha": float(alpha), "cv": cv})
        print(f"{float(alpha):8.4f} | {cv:7.4f}")
    # 同分时选"最简单"（alpha 最大）的模型：CV 差 0.005 以内都算打平
    best_cv = max(r["cv"] for r in alpha_rows)
    tied = [r for r in alpha_rows if r["cv"] >= best_cv - 0.005]
    best_alpha = max(tied, key=lambda r: r["alpha"])["alpha"]

    full = DecisionTree(max_depth=best_depth, criterion=best_criterion).fit(X_tr, y_tr)
    pruned = DecisionTree(max_depth=best_depth, criterion=best_criterion,
                          ccp_alpha=best_alpha).fit(X_tr, y_tr)
    print(f"\n选中：depth={best_depth}，criterion={best_criterion}，ccp_alpha={best_alpha:.4f}")
    print(f"{'模型':10} | {'测试 acc':>8} | {'叶子':>4}")
    print("-" * 30)
    for name, model in (("完整", full), ("剪枝", pruned)):
        print(f"{name:10} | {accuracy(y_te, model.predict(X_te)):8.4f} | "
              f"{model.get_n_leaves():4d}")

    # 稳定性：bootstrap 20 棵树，看测试预测分歧
    rng = np.random.default_rng(0)
    preds = []
    for _ in range(20):
        idx = rng.integers(0, len(y_tr), len(y_tr))
        boot = DecisionTree(max_depth=best_depth, criterion=best_criterion,
                            ccp_alpha=best_alpha).fit(X_tr[idx], y_tr[idx])
        preds.append(boot.predict(X_te))
    preds = np.array(preds)
    disagree = float(np.mean([np.mean(preds[i] != preds[j])
                              for i in range(20) for j in range(i + 1, 20)]))

    test_full = accuracy(y_te, full.predict(X_te))
    test_pruned = accuracy(y_te, pruned.predict(X_te))
    pred_classes = set(np.unique(pruned.predict(X_te)).tolist())

    print(f"\nbootstrap 20 棵剪枝树：测试预测两两分歧均值 {disagree:.4f}")
    print("\n== 验收 ==")
    checks = [
        ("CV 最优深度在 2–6 之间", 2 <= best_depth <= 6),
        ("完整树测试准确率 ≥ 0.85", test_full >= 0.85),
        ("剪枝后测试准确率 ≥ 0.85", test_pruned >= 0.85),
        ("剪枝后叶子数 < 完整树", pruned.get_n_leaves() < full.get_n_leaves()),
        ("测试集覆盖 3 个类别", len(pred_classes) == 3),
        ("bootstrap 分歧 ≥ 0.02（树确实不稳定）", disagree >= 0.02),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"

    print(f"\n→ 真实三分类：完整树 {test_full:.3f}、剪枝 {test_pruned:.3f}、"
          f"{pruned.get_n_leaves()} 叶；换样本后约 {disagree:.0%} 的测试预测会变。")


if __name__ == "__main__":
    main()
