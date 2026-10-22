"""迁移项目：乳腺癌数据上的感知机 vs 逻辑回归

    uv run python breast_cancer.py

真实数据（569×30），不是线性可分；重点看：
- 感知机在真实重叠数据上的准确率/AUC；
- 与 sklearn 感知机是否一致；
- 与逻辑回归的差距（概率/间隔）；
- 误差不归零时，感知机仍在"震荡"。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import framework  # noqa: E402
from impl import Perceptron  # noqa: E402


def acc(y, p):
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    X, y = load_breast_cancer(return_X_y=True)
    y = np.where(y == 1, 1, -1)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
    print(f"样本 {len(y)}（训练 {len(y_tr)} / 测试 {len(y_te)}），特征 {X.shape[1]} 维")

    hand = Perceptron(lr=0.01, epochs=200, random_state=0).fit(X_tr, y_tr)
    sk = framework.fit_perceptron(X_tr, y_tr, lr=0.01, epochs=200)
    log = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(X_tr, y_tr)

    rows = {}
    for name, model, score in (
        ("手写感知机", hand, hand.decision_function),
        ("sklearn 感知机", sk, sk.decision_function),
        ("逻辑回归", log, log.decision_function),
    ):
        pred = model.predict(X_te)
        rows[name] = {
            "acc": acc(y_te, pred),
            "f1": float(f1_score(y_te, pred, pos_label=1)),
            "auc": float(roc_auc_score(y_te, score(X_te))),
        }

    print(f"\n{'方法':14} | {'acc':>6} | {'F1':>6} | {'AUC':>6}")
    print("-" * 38)
    for name, r in rows.items():
        print(f"{name:14} | {r['acc']:6.3f} | {r['f1']:6.3f} | {r['auc']:6.3f}")
    print(f"\n手写感知机：{hand.epochs_run} 轮，最后一轮错误 {hand.errors_per_epoch[-1]}，"
          f"间隔 {hand.margin:.3f}")
    log_margin = 2.0 / np.linalg.norm(log.named_steps["logisticregression"].coef_[0])
    print(f"逻辑回归间隔：{log_margin:.3f}（标准化空间）")

    print("\n== 验收 ==")
    checks = [
        ("手写感知机 acc ≥ 0.90", rows["手写感知机"]["acc"] >= 0.90),
        ("与 sklearn acc 差 ≤ 0.02",
         abs(rows["手写感知机"]["acc"] - rows["sklearn 感知机"]["acc"]) <= 0.02),
        ("逻辑回归不差于感知机", rows["逻辑回归"]["acc"] >= rows["手写感知机"]["acc"] - 0.02),
        ("手写 AUC ≥ 0.95", rows["手写感知机"]["auc"] >= 0.95),
        ("真实数据上误差不归零", hand.errors_per_epoch[-1] > 0),
        ("间隔 > 0", hand.margin > 0),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"

    print("\n→ 真实数据不可分：感知机误差不归零，但准确率/AUC 仍可用；"
          "逻辑回归的概率与间隔更稳。")


if __name__ == "__main__":
    main()
