"""迁移项目：8×8 手写数字上的 LeNet —— 手写 vs torch vs 线性基线

    uv run python digits.py

真实 digits（1797 张，10 类），训练 1400 / 测试 397。
重点：小 LeNet 的卷积/池化/BN/残差是否真的比线性基线强，以及手写与 torch 的差距。
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
from impl import LeNet  # noqa: E402


def acc(y, p):
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 1, 8, 8)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, train_size=1400, random_state=0,
                                              stratify=y)
    print(f"样本 {len(y)}（训练 {len(X_tr)} / 测试 {len(X_te)}），8×8，10 类")

    t0 = time.perf_counter()
    hand = LeNet(lr=0.003, epochs=100, batch_size=64, use_bn=True,
                 use_residual=True, random_state=0).fit(X_tr, y_tr)
    t_hand = time.perf_counter() - t0
    t0 = time.perf_counter()
    torch_model = framework.TorchLeNet(lr=0.003, epochs=100, batch_size=64,
                                       use_bn=True, use_residual=True,
                                       random_state=0).fit(X_tr, y_tr)
    t_torch = time.perf_counter() - t0
    baseline = LeNet(lr=0.003, epochs=100, batch_size=64, random_state=0).fit(X_tr, y_tr)
    log = LogisticRegression(max_iter=5000).fit(X_tr.reshape(len(X_tr), -1), y_tr)

    print(f"\n{'方法':14} | {'测试 acc':>8} | {'macro F1':>8} | {'耗时(s)':>7}")
    print("-" * 46)
    rows = {}
    for name, model, t in (("手写 LeNet", hand, t_hand),
                           ("torch LeNet", torch_model, t_torch),
                           ("逻辑回归", log, 0.0)):
        pred = model.predict(X_te if name != "逻辑回归" else X_te.reshape(len(X_te), -1))
        rows[name] = {"acc": acc(y_te, pred),
                      "f1": float(f1_score(y_te, pred, average="macro"))}
        print(f"{name:14} | {rows[name]['acc']:8.4f} | {rows[name]['f1']:8.4f} | {t:7.2f}")

    base_acc = acc(y_te, baseline.predict(X_te))
    print(f"\nbaseline（无 BN/残差）：{base_acc:.4f}；BN+残差：{rows['手写 LeNet']['acc']:.4f}")
    print("\n== 验收 ==")
    checks = [
        ("手写 LeNet acc ≥ 0.90", rows["手写 LeNet"]["acc"] >= 0.90),
        ("torch LeNet acc ≥ 0.95", rows["torch LeNet"]["acc"] >= 0.95),
        ("手写 vs torch 差 ≤ 0.06",
         abs(rows["手写 LeNet"]["acc"] - rows["torch LeNet"]["acc"]) <= 0.06),
        ("手写 macro F1 ≥ 0.90", rows["手写 LeNet"]["f1"] >= 0.90),
        ("BN+残差比 baseline 高", rows["手写 LeNet"]["acc"] > base_acc),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print("\n→ 8×8 小图上 LeNet 约 0.94；线性基线很强，CNN 的收益要在更大图像上才明显。")


if __name__ == "__main__":
    main()
