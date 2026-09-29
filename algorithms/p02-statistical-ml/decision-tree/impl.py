"""决策树 ID3 / CART — 手写实现（监督估计器）

接口是 fit / predict，但**没有梯度下降**——树的生长是递归划分。本实验要手写
的核心是**划分准则本身**（ID3 的信息增益 / CART 的基尼指数），所以在 impl 里
必须写出熵与基尼的逐行计算，而不是调库。

    tree = DecisionTree(criterion="gini", max_depth=5, min_samples_split=2)
    tree.fit(X_train, y_train)
    label = tree.predict(X_test)

**本目录自带"基线对照"**：不调 sklearn，而是用"多数类预测"作为下限基线——
树再差也不该比它差。sklearn 的 DecisionTreeClassifier 作为框架对照放在
framework.py，用来看"框架多做了什么优化"（预排序、分箱、剪枝）。
"""

from typing import Any

import numpy as np

Node = dict


def entropy(y: np.ndarray) -> float:
    """ID3 的划分准则：H(D) = -Σ p_k log2 p_k（p_k 为第 k 类占比）。"""
    # TODO: 手写——注意 p=0 时 p*log2(p) 记为 0（别让 log 出 -inf）
    raise NotImplementedError("TODO: 手写信息熵")


def gini(y: np.ndarray) -> float:
    """CART 的划分准则：Gini(D) = 1 - Σ p_k^2（比熵少一次 log，工程上更常用）。"""
    # TODO: 手写
    raise NotImplementedError("TODO: 手写基尼指数")


class DecisionTree:
    """决策树：按 criterion 选最优划分特征与切分点，递归生长。"""

    def __init__(
        self,
        criterion: str = "gini",
        max_depth: int | None = None,
        min_samples_split: int = 2,
    ) -> None:
        self.criterion = criterion
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.root: Node | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "DecisionTree":
        """递归建树，返回根节点；节点结构自定，README「目录形态」段要写清。"""
        # TODO: 手写
        #   1. 终止条件：全同类 / 达 max_depth / 样本数 < min_samples_split → 叶子（存多数类）
        #   2. 否则遍历每个特征的每个候选切分点，按 criterion 算加权不纯度增益
        #   3. 取增益最大者划分，左右子集递归
        #   4. 连续特征要写清候选切分点怎么取（排序后取相邻中点即可，README 说明复杂度）
        raise NotImplementedError("TODO: 手写递归建树")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: 每条样本从 root 按划分条件落到叶子，取叶子类别
        raise NotImplementedError("TODO: 手写逐样本下推")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
