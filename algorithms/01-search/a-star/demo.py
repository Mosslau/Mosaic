"""A* 启发式搜索 — demo：同数据双跑 + 可视化对比

要求：
1. 用一个小而经典的数据集（能几分钟内跑完）
2. 同一份 train/test 切分，分别跑手写版（impl.py）和框架版（framework.py）
3. 输出两套关键指标并排对比
4. 至少一张可视化图（matplotlib），含手写 vs 框架的对比
5. 结论写回本目录 README.md 的「实验结果」一节
"""

import time

from impl import Model
from framework import run_framework


def load_data():
    """TODO: 加载数据集，返回 X_train, X_test, y_train, y_test（固定随机种子保证可复现）。"""
    raise NotImplementedError


def evaluate(y_true, y_pred) -> dict:
    """TODO: 返回本任务的关键指标，如 {'mse': ..., 'mae': ...}"""
    raise NotImplementedError


def main() -> None:
    X_train, X_test, y_train, y_test = load_data()

    # --- 手写实现 ---
    t0 = time.perf_counter()
    model = Model()
    model.fit(X_train, y_train)
    pred_manual = model.predict(X_test)
    t_manual = time.perf_counter() - t0
    metrics_manual = evaluate(y_test, pred_manual)

    # --- 框架对照 ---
    t0 = time.perf_counter()
    metrics_framework = run_framework(X_train, X_test, y_train, y_test)
    t_framework = time.perf_counter() - t0

    # --- 并排对比 ---
    print(f"{'':12} | {'手写实现':>12} | {'框架调用':>12}")
    print("-" * 44)
    for k, v in metrics_manual.items():
        print(f"{k:12} | {v:>12.4f} | {metrics_framework.get(k, float('nan')):>12.4f}")
    print(f"{'time_sec':12} | {t_manual:>12.4f} | {t_framework:>12.4f}")

    # TODO: 可视化对比（matplotlib），保存图片到本目录


if __name__ == "__main__":
    main()
