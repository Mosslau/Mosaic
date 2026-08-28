"""蒙特卡洛树搜索 MCTS — 手写实现

原则：只用 numpy 手写核心逻辑，禁止调 sklearn/torch 的现成算法接口。
（数据加载、可视化可以用现成工具）
"""

import numpy as np


class Model:
    """算法核心实现。"""

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Model":
        raise NotImplementedError("TODO: 手写训练逻辑")

    def predict(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError("TODO: 手写推理逻辑")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
