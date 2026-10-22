"""迁移项目：把 8×8 数字的每一行当序列 —— RNN vs LSTM

    uv run python digits.py

输入 `(N, 8, 8)`：8 个时间步，每步 8 个像素特征；输出 10 类。
对比 RNN 与 LSTM 的测试 acc/F1/耗时；这是“序列模型用在非文本数据”的最小例子。
"""

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import LSTM, RNN  # noqa: E402


def acc(y, p):
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 8, 8)       # 每行 = 一个时间步
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, train_size=1200, random_state=0,
                                              stratify=y)
    print(f"样本 {len(y)}（训练 {len(X_tr)} / 测试 {len(X_te)}），T=8，input=8，10 类")

    print(f"\n{'模型':8} | {'测试 acc':>8} | {'macro F1':>8} | {'耗时(s)':>7}")
    print("-" * 40)
    rows = {}
    for name, cls in (("RNN", RNN), ("LSTM", LSTM)):
        t0 = time.perf_counter()
        m = cls(input_size=8, hidden_size=32, n_classes=10, lr=0.01, epochs=40,
                batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr)
        t = time.perf_counter() - t0
        pred = m.predict(X_te)
        rows[name] = {"acc": acc(y_te, pred),
                      "f1": float(f1_score(y_te, pred, average="macro"))}
        print(f"{name:8} | {rows[name]['acc']:8.4f} | {rows[name]['f1']:8.4f} | {t:7.2f}")

    print("\n== 验收 ==")
    checks = [
        ("LSTM 测试 acc ≥ 0.98", rows["LSTM"]["acc"] >= 0.98),
        ("RNN 测试 acc ≥ 0.95", rows["RNN"]["acc"] >= 0.95),
        ("LSTM 比 RNN 高", rows["LSTM"]["acc"] > rows["RNN"]["acc"]),
        ("LSTM macro F1 ≥ 0.98", rows["LSTM"]["f1"] >= 0.98),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print("\n→ 8 行序列上 LSTM 略优于 RNN；序列模型也能处理非文本数据。")


if __name__ == "__main__":
    main()
