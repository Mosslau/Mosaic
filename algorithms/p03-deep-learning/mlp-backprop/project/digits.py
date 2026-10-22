"""迁移项目：手写数字 10 分类 —— MLP vs torch vs 逻辑回归

    uv run python digits.py

真实 8×8 像素（1797 张），训练 1200 / 测试 597。
重点：手写反向传播的 MLP 能否达到可用精度，与 torch 差多少，比线性基线强多少。
"""

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import framework  # noqa: E402
from impl import MLP  # noqa: E402


def acc(y, p):
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, train_size=1200, random_state=0, stratify=y)
    print(f"样本 {len(y)}（训练 {len(X_tr)} / 测试 {len(X_te)}），特征 {X.shape[1]} 维，10 类")

    t0 = time.perf_counter()
    hand = MLP(hidden_sizes=(64, 32), lr=0.01, epochs=40, batch_size=32,
               optimizer="adam", init="he", random_state=0).fit(X_tr, y_tr)
    t_hand = time.perf_counter() - t0
    t0 = time.perf_counter()
    torch_model = framework.fit_torch_mlp(X_tr, y_tr, hidden_sizes=(64, 32), lr=0.01,
                                          epochs=40, batch_size=32, optimizer="adam",
                                          init="he", random_state=0)
    t_torch = time.perf_counter() - t0

    log = LogisticRegression(max_iter=5000).fit(X_tr, y_tr)

    print(f"\n{'方法':14} | {'测试 acc':>8} | {'macro F1':>8} | {'耗时(s)':>7}")
    print("-" * 46)
    rows = {}
    for name, model, t in (("手写 MLP", hand, t_hand),
                           ("torch MLP", torch_model, t_torch),
                           ("逻辑回归", log, 0.0)):
        pred = model.predict(X_te)
        rows[name] = {"acc": acc(y_te, pred),
                      "f1": float(f1_score(y_te, pred, average="macro"))}
        print(f"{name:14} | {rows[name]['acc']:8.4f} | {rows[name]['f1']:8.4f} | {t:7.2f}")

    print(f"\n手写 MLP：{hand.epochs_run} 轮，末轮 loss {hand.loss_history[-1]:.4f}")
    print("\n== 验收 ==")
    checks = [
        ("手写 MLP 测试 acc ≥ 0.95", rows["手写 MLP"]["acc"] >= 0.95),
        ("torch MLP 测试 acc ≥ 0.95", rows["torch MLP"]["acc"] >= 0.95),
        ("手写 vs torch 差 ≤ 0.03",
         abs(rows["手写 MLP"]["acc"] - rows["torch MLP"]["acc"]) <= 0.03),
        ("手写 macro F1 ≥ 0.95", rows["手写 MLP"]["f1"] >= 0.95),
        ("MLP 比逻辑回归高 ≥ 0.005",
         rows["手写 MLP"]["acc"] - rows["逻辑回归"]["acc"] >= 0.005),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print("\n→ 非线性 MLP 略强于线性基线；手写与 torch 同量级，差异来自初始化/算子顺序。")


if __name__ == "__main__":
    main()
