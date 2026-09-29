"""朴素贝叶斯 — 手写实现（监督估计器）

本族的异类：**没有训练循环、没有梯度**，fit 只是数频次（参数估计）。
要手写的是概率本身——先验、条件概率、以及对"条件独立假设"的取舍。

    nb = NaiveBayes(alpha=1.0)          # alpha 是拉普拉斯平滑系数
    nb.fit(X_train, y_train)
    label = nb.predict(X_test)
    proba = nb.predict_proba(X_test)

两个必须自己实现的点（README「数学推导」段要写出推导）：
    1. 对数域计算：连乘容易下溢，所有概率转 log 后相加
    2. 拉普拉斯平滑：某特征值在某类中没出现过时概率为 0，会把整条后验打成 0
"""

import numpy as np


class NaiveBayes:
    """朴素贝叶斯分类器（支持离散特征；连续特征请先自行离散化并在 demo 里说明）。"""

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self.classes_: np.ndarray | None = None
        self.log_prior: dict = {}
        self.log_likelihood: dict = {}

    def fit(self, X: np.ndarray, y: np.ndarray) -> "NaiveBayes":
        """纯计数式参数估计，无迭代。"""
        # TODO: 手写
        #   1. 统计类先验 P(c)（取 log）
        #   2. 对每个特征、每个取值、每个类统计条件概率 P(x_i | c)
        #   3. 拉普拉斯平滑：分子 + alpha，分母 + alpha * 该特征取值数
        #   4. 全部转 log 存起来，predict 时只做加法（避免连乘下溢）
        raise NotImplementedError("TODO: 手写概率表估计")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        # TODO: log 后验 = log 先验 + Σ log 条件概率；用 logsumexp 归一化成概率
        raise NotImplementedError("TODO: 手写对数后验")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: 取后验最大的类（log 域里就是取最大，不必真归一化）
        raise NotImplementedError("TODO: 手写后验判决")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
