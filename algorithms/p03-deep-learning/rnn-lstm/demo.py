"""RNN 与 LSTM — demo：合成序列、BPTT、梯度裁剪与梯度范数

    uv run python demo.py

    实验一  parity 任务：RNN vs LSTM（T=12）
    实验二  梯度范数（对 h0）随 T 的变化
    实验三  高学习率下的梯度裁剪
    实验四  torch 对照
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import LSTM, RNN

SEED = 0


def make_parity(n: int = 5000, T: int = 12, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(n, T))
    y = X.sum(axis=1) % 2
    return np.eye(2)[X], y


def split_data(n: int = 5000, T: int = 12):
    X, y = make_parity(n, T)
    cut = int(n * 0.8)
    return X[:cut], X[cut:], y[:cut], y[cut:]


def acc(y, p) -> float:
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def _median_time(fn, repeats=2):
    times, result = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


def experiment_parity() -> None:
    X_tr, X_te, y_tr, y_te = split_data()
    print("== 实验一：parity 任务（T=12，4000/1000） ==")
    print(f"{'模型':10} | {'训练 acc':>8} | {'测试 acc':>8} | {'末轮 loss':>9} | {'耗时(s)':>7}")
    print("-" * 56)
    results = {}
    for name, cls in (("RNN", RNN), ("LSTM", LSTM)):
        m, t = _median_time(lambda cls=cls: cls(input_size=2, hidden_size=32, n_classes=2,
                                                lr=0.01, epochs=40, batch_size=32,
                                                clip_norm=1.0, random_state=SEED).fit(X_tr, y_tr))
        results[name] = m
        print(f"{name:10} | {acc(y_tr, m.predict(X_tr)):8.4f} | "
              f"{acc(y_te, m.predict(X_te)):8.4f} | {m.loss_history[-1]:9.4f} | {t:7.2f}")
    assert acc(y_te, results["LSTM"].predict(X_te)) > 0.9
    assert acc(y_te, results["RNN"].predict(X_te)) < 0.7
    print("\n→ LSTM 能学到长程 parity；RNN 在 T=12 上基本停在随机水平。\n")


def experiment_grad_norm(models) -> None:
    print("== 实验二：h0 梯度范数随 T（5 批平均） ==")
    print(f"{'T':>3} | {'RNN':>12} | {'LSTM':>12}")
    print("-" * 34)
    for T in (4, 8, 16, 32, 48):
        vals = {}
        for name, m in models.items():
            gs = []
            for seed in range(5):
                X, y = make_parity(200, T, seed=seed)
                gs.append(m.grad_norm_h0_for_T(X, y))
            vals[name] = float(np.mean(gs))
        print(f"{T:3d} | {vals['RNN']:12.6f} | {vals['LSTM']:12.6f}")
    assert vals["LSTM"] > vals["RNN"]
    print("\n→ RNN 的 h0 梯度随 T 迅速衰减；LSTM 的门控/细胞状态把它保住。\n")


def experiment_clipping() -> None:
    X_tr, X_te, y_tr, y_te = split_data(2000, 20)
    print("== 实验三：高学习率（0.5）下的梯度裁剪（T=20） ==")
    print(f"{'clip_norm':10} | {'测试 acc':>8} | {'末轮 loss':>9} | {'平均梯度范数':>12}")
    print("-" * 50)
    for clip in (None, 1.0):
        m = RNN(input_size=2, hidden_size=32, n_classes=2, lr=0.5, epochs=10,
                batch_size=32, clip_norm=clip, random_state=0).fit(X_tr, y_tr)
        print(f"{str(clip):10} | {acc(y_te, m.predict(X_te)):8.4f} | "
              f"{m.loss_history[-1]:9.4f} | {np.mean(m.grad_norm_history):12.3f}")
    print("\n→ 裁剪把更新步长压住，梯度范数从几十降到个位数；但不保证准确率提升。\n")


def experiment_torch() -> None:
    X_tr, X_te, y_tr, y_te = split_data()
    print("== 实验四：手写 vs torch（T=12） ==")
    for cell, hand_cls in (("rnn", RNN), ("lstm", LSTM)):
        hand = hand_cls(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=40,
                        batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr)
        torch_model = framework.TorchSequence(cell=cell, input_size=2, hidden_size=32,
                                              n_classes=2, lr=0.01, epochs=40,
                                              batch_size=32, clip_norm=1.0,
                                              random_state=0).fit(X_tr, y_tr)
        print(f"{cell:5} 手写 {acc(y_te, hand.predict(X_te)):.3f}；"
              f"torch {acc(y_te, torch_model.predict(X_te)):.3f}")
    print()


def main() -> None:
    experiment_parity()
    # 复用实验一训好的模型做梯度范数诊断
    X_tr, _, y_tr, _ = split_data()
    models = {
        "RNN": RNN(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=40,
                   batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr),
        "LSTM": LSTM(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=40,
                     batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr),
    }
    experiment_grad_norm(models)
    experiment_clipping()
    experiment_torch()


if __name__ == "__main__":
    main()
