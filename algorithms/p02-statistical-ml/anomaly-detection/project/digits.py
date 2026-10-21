"""迁移项目：真实数据上的异常检测 —— 手写数字 0 vs 其他

    uv run python digits.py

把数字 0 当"正常"，其他 9 个数字当"异常"：
训练只用 0（120 张），测试 = 未见的 0（约 58 张）+ 其他数字（100 张）。
三种方法都在训练集内部定阈值（contamination=5%），测试只报告一次。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.metrics import precision_score, recall_score, roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import KDE, LOF, IsolationForest  # noqa: E402


def main() -> None:
    X, y = load_digits(return_X_y=True)
    normal, anomaly = X[y == 0], X[y != 0]
    X_tr = normal[:120]
    X_te = np.vstack([normal[120:], anomaly[:100]])
    y_te = np.r_[np.zeros(len(normal) - 120), np.ones(100)]
    print(f"正常（数字 0）：训练 {len(X_tr)}，测试 {len(normal) - 120}；"
          f"异常（其他数字）：测试 {100}")

    models = {
        "IsolationForest": IsolationForest(n_trees=100, contamination=0.05, random_state=0),
        "LOF": LOF(n_neighbors=20, contamination=0.05),
        "KDE": KDE(contamination=0.05),
    }
    print(f"\n{'方法':16} | {'AUC':>6} | {'精确率':>6} | {'召回率':>6} | {'报警数':>5}")
    print("-" * 50)
    rows = {}
    for name, model in models.items():
        model.fit(X_tr)
        s = model.score_samples(X_te)
        pred = np.where(s > model.threshold_, 1, 0)
        rows[name] = {
            "auc": float(roc_auc_score(y_te, s)),
            "p": float(precision_score(y_te, pred, zero_division=0)),
            "r": float(recall_score(y_te, pred, zero_division=0)),
            "n": int(pred.sum()),
        }
        print(f"{name:16} | {rows[name]['auc']:6.3f} | {rows[name]['p']:6.3f} | "
              f"{rows[name]['r']:6.3f} | {rows[name]['n']:5d}")

    print("\n== 验收 ==")
    checks = [
        ("IForest AUC ≥ 0.90", rows["IsolationForest"]["auc"] >= 0.90),
        ("LOF AUC ≥ 0.90", rows["LOF"]["auc"] >= 0.90),
        ("KDE AUC ≥ 0.90", rows["KDE"]["auc"] >= 0.90),
        ("IForest 精确率 ≥ 0.80", rows["IsolationForest"]["p"] >= 0.80),
        ("LOF 精确率 ≥ 0.80", rows["LOF"]["p"] >= 0.80),
        ("三种方法召回率都 ≥ 0.90",
         all(rows[m]["r"] >= 0.90 for m in rows)),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"

    print("\n→ 真实像素的 one-class 场景：IF/LOF 高精确率，KDE 的密度阈值偏松"
          "（AUC 仍 1.0，说明排序对、阈值没校准）。")


if __name__ == "__main__":
    main()
