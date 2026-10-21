"""参考解：第 3 题（判断）——三个异常检测 bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import IsolationForest  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402


def main() -> None:
    X_tr, X_te, y = D.make_data()

    print("A 训练集混入异常：")
    clean = IsolationForest(random_state=0).fit(X_tr)
    rng = np.random.default_rng(0)
    dirty_X = np.vstack([X_tr, rng.normal([4, 4], 0.5, size=(20, 2))])
    dirty = IsolationForest(random_state=0).fit(dirty_X)
    rec_clean = float(np.mean(dirty.predict(X_te[y == 1]) == 1))
    rec_clean0 = float(np.mean(clean.predict(X_te[y == 1]) == 1))
    print(f"   干净训练：阈值 {clean.threshold_:.3f}，异常召回 {rec_clean0:.3f}")
    print(f"   污染训练：阈值 {dirty.threshold_:.3f}，异常召回 {rec_clean:.3f}")
    assert dirty.threshold_ >= clean.threshold_ - 1e-9

    print("\nB 分数方向反了：")
    s = clean.score_samples(X_te)
    print(f"   正确 AUC {roc_auc_score(y, s):.3f}；取负后 {roc_auc_score(y, -s):.3f}")
    assert roc_auc_score(y, -s) < 0.5

    print("\nC 用测试集定阈值（泄漏）：")
    s = clean.score_samples(X_te)

    def f1_at(tau):
        pred = (s > tau).astype(int)
        tp = np.sum((pred == 1) & (y == 1))
        fp = np.sum((pred == 1) & (y == 0))
        fn = np.sum((pred == 0) & (y == 1))
        return 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)

    f1_train = f1_at(clean.threshold_)
    # 在测试集上挑一个最优阈值（oracle，泄漏）
    taus = np.quantile(s, np.linspace(0.5, 0.99, 50))
    f1_oracle = max(f1_at(t) for t in taus)
    print(f"   训练阈值下 F1 {f1_train:.3f}；在测试集上挑阈值 F1 {f1_oracle:.3f}")
    assert f1_oracle >= f1_train
    print("\n→ A 阈值漂移；B AUC 反转；C 阈值泄漏。")


if __name__ == "__main__":
    main()
