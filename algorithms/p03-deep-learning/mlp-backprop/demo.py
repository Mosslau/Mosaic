"""MLP 与手写反向传播 — demo：手写 vs torch + 训练技巧五组对照

    uv run python demo.py

    实验一  基线：手写 MLP vs torch（digits 10 类）
    实验二  优化器：SGD / Momentum / Adam
    实验三  初始化：zero / random / He / Xavier
    实验四  正则：none / dropout / weight decay
    实验五  LR schedule 与 batch size
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import MLP
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 3


def load_data(n_train: int = 900):
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    return train_test_split(X, y, train_size=n_train, random_state=SEED, stratify=y)


def acc(y, p) -> float:
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def _median_time(fn, repeats: int = REPEATS):
    times, result = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


def _fit_hand(X_tr, y_tr, **kw):
    params = dict(hidden_sizes=(64, 32), lr=0.01, epochs=30, batch_size=32,
                  optimizer="adam", init="he", random_state=SEED)
    params.update(kw)
    return MLP(**params).fit(X_tr, y_tr)


# ---------------------------------------------------------------- 实验一

def experiment_baseline() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    hand, t_hand = _median_time(lambda: _fit_hand(X_tr, y_tr))
    torch_model, t_torch = _median_time(
        lambda: framework.fit_torch_mlp(X_tr, y_tr, hidden_sizes=(64, 32), lr=0.01,
                                        epochs=30, batch_size=32, optimizer="adam",
                                        init="he", random_state=SEED))
    print("== 实验一：手写 MLP vs torch（digits，10 类） ==")
    print(f"{'方法':12} | {'训练 acc':>8} | {'测试 acc':>8} | {'末轮 loss':>9} | {'耗时(ms)':>8}")
    print("-" * 58)
    for name, model, t in (("手写", hand, t_hand), ("torch", torch_model, t_torch)):
        print(f"{name:12} | {acc(y_tr, model.predict(X_tr)):8.4f} | "
              f"{acc(y_te, model.predict(X_te)):8.4f} | {model.loss_history[-1]:9.4f} | "
              f"{t * 1000:8.1f}")
    assert acc(y_te, hand.predict(X_te)) > 0.95
    assert acc(y_te, torch_model.predict(X_te)) > 0.95
    assert abs(acc(y_te, hand.predict(X_te)) - acc(y_te, torch_model.predict(X_te))) < 0.05
    print("\n→ 两边都 >0.95；torch 慢在逐 batch 的框架调用，不是算法差异。\n")


# ---------------------------------------------------------------- 实验二

def experiment_optimizers() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    print("== 实验二：优化器 ==")
    print(f"{'optimizer':10} | {'lr':>5} | {'测试 acc':>8} | {'末轮 loss':>9} | {'轮数':>4}")
    print("-" * 46)
    for opt, lr in (("sgd", 0.05), ("momentum", 0.01), ("adam", 0.01)):
        m = _fit_hand(X_tr, y_tr, optimizer=opt, lr=lr)
        print(f"{opt:10} | {lr:5.2f} | {acc(y_te, m.predict(X_te)):8.4f} | "
              f"{m.loss_history[-1]:9.4f} | {m.epochs_run:4d}")
        assert acc(y_te, m.predict(X_te)) > 0.85
    print("\n→ Adam 在同样 30 轮内最快到高精度；SGD 需要更大 lr 或更多轮。\n")


# ---------------------------------------------------------------- 实验三

def experiment_init() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    print("== 实验三：初始化（Adam, 20 轮） ==")
    print(f"{'init':8} | {'测试 acc':>8} | {'末轮 loss':>9}")
    print("-" * 32)
    results = {}
    for init in ("zero", "random", "he", "xavier"):
        m = _fit_hand(X_tr, y_tr, init=init, epochs=20)
        results[init] = acc(y_te, m.predict(X_te))
        print(f"{init:8} | {results[init]:8.4f} | {m.loss_history[-1]:9.4f}")
    assert results["zero"] < 0.2
    assert results["he"] > 0.9
    print("\n→ 全零初始化对称性破不了，所有隐单元学成一样；He/Xavier 才能正常训练。\n")


# ---------------------------------------------------------------- 实验四

def experiment_regularization() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    print("== 实验四：正则（Adam, 30 轮） ==")
    print(f"{'配置':18} | {'训练 acc':>8} | {'测试 acc':>8} | {'gap':>7}")
    print("-" * 50)
    configs = {
        "none": {},
        "dropout=0.3": {"dropout": 0.3},
        "weight_decay=1e-3": {"weight_decay": 1e-3},
    }
    for name, kw in configs.items():
        m = _fit_hand(X_tr, y_tr, **kw)
        tr, te = acc(y_tr, m.predict(X_tr)), acc(y_te, m.predict(X_te))
        print(f"{name:18} | {tr:8.4f} | {te:8.4f} | {tr - te:7.4f}")
    print("\n→ digits 上模型不算大：dropout/weight decay 反而略降测试 acc、"
          "gap 没缩小；正则不是「加上就更好」，要看数据/模型容量。\n")


# ---------------------------------------------------------------- 实验五

def experiment_schedule_batch() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    print("== 实验五：LR schedule 与 batch size（Adam, 30 轮） ==")
    print(f"{'schedule':10} | {'batch':>5} | {'测试 acc':>8} | {'末轮 lr':>8}")
    print("-" * 42)
    for sched, batch in (("none", 32), ("step", 32), ("cosine", 32),
                         ("none", 16), ("none", 64), ("none", 256)):
        m = _fit_hand(X_tr, y_tr, lr_schedule=sched, batch_size=batch)
        print(f"{sched:10} | {batch:5d} | {acc(y_te, m.predict(X_te)):8.4f} | "
              f"{m.current_lr_:8.4f}")
    print("\n→ schedule 在短训练上收益有限；batch=16 略好但更慢，batch=256 更新次数少、略差。\n")


def main() -> None:
    experiment_baseline()
    experiment_optimizers()
    experiment_init()
    experiment_regularization()
    experiment_schedule_batch()


if __name__ == "__main__":
    main()
