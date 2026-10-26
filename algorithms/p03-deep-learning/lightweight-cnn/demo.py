"""轻量级 CNN：深度可分离卷积 — demo

    uv run python demo.py

    实验一  同数据同轮数三路对照（手写 DS / 手写标准 Conv / torch DS）
    实验二  参数量拆解与压缩比
    实验三  单批前向延迟（batch=128），看"参数少"是否等于"跑得快"
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import MobileNetLite, StandardCNN
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

SEED = 0
EPOCHS = 25
BATCH_SIZE = 64
LR = 0.01
SCALE = 2
N_TRAIN = 1400
BENCH_BATCH = 128
REPEATS = 15


def load_data(n_train: int = N_TRAIN, scale: int = SCALE):
    """digits 8×8 → /16 → 最近邻上采样 scale 倍（默认 16×16）。"""
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 1, 8, 8)
    if scale > 1:
        X = np.repeat(np.repeat(X, scale, axis=2), scale, axis=3)
    return train_test_split(X, y, train_size=n_train, random_state=SEED, stratify=y)


def acc(y, p) -> float:
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def bench_forward(fn, X, warmup: int = 3, repeats: int = REPEATS) -> float:
    """单批前向的毫秒中位数；warmup 排除首次分配/编译开销。"""
    for _ in range(warmup):
        fn(X)
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn(X)
        times.append((time.perf_counter() - t0) * 1000)
    return float(statistics.median(times))


def stage_params(model) -> dict[str, int]:
    if not model._built:
        model.init()
    counts = {"stem": sum(p.size for p, _ in model.stem._params + model.stem_bn._params)}
    for i, block in enumerate(model.blocks, 1):
        counts[f"block{i}"] = sum(p.size for p, _ in block._params)
    counts["head"] = int(model.head_W.size + model.head_b.size)
    assert sum(counts.values()) == model.n_params()
    return counts


def run_experiments(epochs: int = EPOCHS) -> dict:
    """训练三个模型并测参数量/准确率/延迟；make_teaching_assets.py 复用同一份结果。"""
    X_tr, X_te, y_tr, y_te = load_data()
    common = dict(lr=LR, epochs=epochs, batch_size=BATCH_SIZE, random_state=SEED)
    t0 = time.perf_counter()
    hand_ds = MobileNetLite(**common).fit(X_tr, y_tr)
    t_ds = time.perf_counter() - t0
    t0 = time.perf_counter()
    hand_std = StandardCNN(**common).fit(X_tr, y_tr)
    t_std = time.perf_counter() - t0
    t0 = time.perf_counter()
    torch_ds = framework.TorchMobileNetLite(**common).fit(X_tr, y_tr)
    t_torch = time.perf_counter() - t0

    Xb = X_te[:BENCH_BATCH]
    return {
        "epochs": epochs,
        "models": [hand_ds, hand_std, torch_ds],
        "names": ["手写 DS", "手写标准 Conv", "torch DS"],
        "params": [m.n_params() for m in (hand_ds, hand_std, torch_ds)],
        "test_acc": [acc(y_te, m.predict(X_te)) for m in (hand_ds, hand_std, torch_ds)],
        "train_sec": [t_ds, t_std, t_torch],
        "latency_ms": [bench_forward(m.predict_proba, Xb)
                       for m in (hand_ds, hand_std, torch_ds)],
        "stage_ds": stage_params(hand_ds),
        "stage_std": stage_params(hand_std),
        "loss": [m.history["loss"] for m in (hand_ds, hand_std, torch_ds)],
        "train_acc_hist": [m.history["train_acc"] for m in (hand_ds, hand_std, torch_ds)],
        "n_test": len(y_te),
    }


def main() -> None:
    res = run_experiments()
    print(f"== 实验一：三路对照（16×16 digits，{res['epochs']} 轮，batch {BATCH_SIZE}） ==")
    print(f"{'方法':18} | {'参数量':>7} | {'测试 acc':>8} | {'训练(s)':>7}")
    print("-" * 52)
    for name, p, a, t in zip(res["names"], res["params"], res["test_acc"], res["train_sec"]):
        print(f"{name:18} | {p:7d} | {a:8.4f} | {t:7.2f}")

    assert res["params"][0] == res["params"][2], "手写 DS 与 torch DS 参数量应完全一致"
    assert res["params"][1] / res["params"][0] > 5.0
    assert min(res["test_acc"]) > 0.9
    print(f"\n→ 手写与 torch 参数量一致（{res['params'][0]}）；"
          f"标准 Conv 是它的 {res['params'][1] / res['params'][0]:.2f} 倍。")
    print(f"  测试集 {res['n_test']} 张，手写 DS 与 torch DS 差 "
          f"{abs(res['test_acc'][0] - res['test_acc'][2]):.4f}。\n")

    print("== 实验二：参数量拆解 ==")
    print(f"{'阶段':8} | {'DS':>6} | {'标准 Conv':>9} | {'压缩比':>6}")
    print("-" * 40)
    for key in res["stage_ds"]:
        ds, std = res["stage_ds"][key], res["stage_std"][key]
        print(f"{key:8} | {ds:6d} | {std:9d} | {std / ds:6.2f}×")
    total_ds, total_std = res["params"][0], res["params"][1]
    print(f"{'合计':8} | {total_ds:6d} | {total_std:9d} | {total_std / total_ds:6.2f}×")
    print("→ DS 块省在 3×3 空间卷积：标准卷积 9·Cin·Cout vs depthwise 9·Cin；"
          "\n  代价是 pointwise 1×1 的 Cin·Cout。\n")

    print(f"== 实验三：单批前向延迟（batch={BENCH_BATCH}，{REPEATS} 次中位数） ==")
    for name, ms in zip(res["names"], res["latency_ms"]):
        print(f"  {name:18} {ms:7.3f} ms")
    assert all(ms > 0 for ms in res["latency_ms"])
    print(f"→ 参数少不等于等比例加速：手写 DS 比标准 Conv 快 "
          f"{res['latency_ms'][1] / res['latency_ms'][0]:.2f}×，"
          f"参数却只有 1/{res['params'][1] / res['params'][0]:.2f}；"
          f"torch 用融合 kernel，又比手写快 {res['latency_ms'][0] / res['latency_ms'][2]:.2f}×。\n")


if __name__ == "__main__":
    main()
